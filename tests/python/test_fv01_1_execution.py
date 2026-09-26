"""FV-01.1 checkpoint contract, execution states, and refusal to fake a run."""

from __future__ import annotations

from pathlib import Path

import pytest

from engines.segmentation.fv01_checkpoint_contract import extract_checkpoint_contract
from engines.segmentation.fv01_execution import (
    DISCOVERED_CHECKPOINT,
    classify_execution,
    run_fv01_execution,
)

PINNED = "100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803"


def _facts(**overrides: object) -> dict:
    facts = {
        "driver_visible": True,
        "nvidia_smi_present": True,
        "torch_available": True,
        "cuda_available": True,
        "cuda_tensor_executed": True,
        "pointops_available": True,
        "checkpoint_present": True,
        "checkpoint_hash_matches": True,
        "model_load_failed": False,
        "tensor_contract_rederived": True,
        "source_revision_matches": True,
        "onnx_states": [],
        "input_invalid": False,
        "inference_failed": False,
        "inference_succeeded": False,
    }
    facts.update(overrides)
    return facts


def test_ready_requires_every_runtime_fact() -> None:
    report = classify_execution(_facts())
    assert report["primary_state"] == "READY"
    assert report["exit_code"] == 0


def test_driver_failure_is_not_collapsed_into_missing_pytorch() -> None:
    report = classify_execution(
        _facts(
            driver_visible=False,
            nvidia_smi_present=True,
            torch_available=False,
            cuda_available=False,
            cuda_tensor_executed=False,
            pointops_available=False,
            onnx_states=["ONNX_UNAVAILABLE", "ONNX_BACKEND_NOT_READY"],
        )
    )
    assert report["primary_state"] == "DRIVER_UNAVAILABLE"
    assert report["applicable_states"][:4] == [
        "DRIVER_UNAVAILABLE",
        "PYTORCH_UNAVAILABLE",
        "POINTOPS_UNAVAILABLE",
        "ONNX_UNAVAILABLE",
    ]
    assert "ONNX_BACKEND_NOT_READY" in report["applicable_states"]
    assert "MODEL_CONTRACT_UNKNOWN" not in report["applicable_states"]
    assert report["ready"] is False


def test_missing_gpu_without_nvidia_smi_is_gpu_unavailable() -> None:
    report = classify_execution(
        _facts(driver_visible=False, nvidia_smi_present=False, torch_available=True)
    )
    assert report["primary_state"] == "GPU_UNAVAILABLE"
    assert "DRIVER_UNAVAILABLE" not in report["applicable_states"]


def test_cuda_unavailable_is_distinct_when_torch_imports() -> None:
    report = classify_execution(
        _facts(cuda_available=False, cuda_tensor_executed=False, pointops_available=True)
    )
    assert report["primary_state"] == "CUDA_UNAVAILABLE"
    assert "PYTORCH_UNAVAILABLE" not in report["applicable_states"]


def test_pointops_model_and_contract_failures_stay_distinct() -> None:
    missing_ops = classify_execution(_facts(pointops_available=False))
    missing_model = classify_execution(
        _facts(checkpoint_present=False, tensor_contract_rederived=False)
    )
    load_failed = classify_execution(
        _facts(model_load_failed=True, tensor_contract_rederived=False)
    )
    unknown = classify_execution(_facts(tensor_contract_rederived=False))
    assert missing_ops["primary_state"] == "POINTOPS_UNAVAILABLE"
    assert missing_model["primary_state"] == "MODEL_MISSING"
    assert load_failed["primary_state"] == "MODEL_LOAD_FAILED"
    assert unknown["primary_state"] == "MODEL_CONTRACT_UNKNOWN"


def test_input_invalid_does_not_hide_a_driver_blocker() -> None:
    report = classify_execution(
        _facts(driver_visible=False, nvidia_smi_present=True, input_invalid=True)
    )
    assert report["primary_state"] == "DRIVER_UNAVAILABLE"
    assert "INPUT_INVALID" in report["applicable_states"]


def test_inference_failure_and_success_are_not_ready() -> None:
    failed = classify_execution(_facts(inference_failed=True))
    succeeded = classify_execution(
        _facts(inference_succeeded=True, onnx_states=["ONNX_UNAVAILABLE"])
    )
    assert failed["primary_state"] == "INFERENCE_FAILED"
    assert failed["ready"] is False
    assert succeeded["primary_state"] == "INFERENCE_SUCCEEDED"
    assert "ONNX_UNAVAILABLE" in succeeded["applicable_states"]


def test_checkpoint_hash_and_tensor_contract_from_the_pinned_file() -> None:
    if not DISCOVERED_CHECKPOINT.is_file():
        pytest.skip("pinned instseg_full.ckpt is not on this machine")
    report = run_fv01_execution(
        hash_checkpoint=True, extract_contract=True, attempt_inference=False
    )
    checkpoint = report["checkpoint"]
    contract = report["contract"]
    assert checkpoint["sha256"] == PINNED
    assert checkpoint["matches_pinned_digest"] is True
    assert contract["state"] == "TENSOR_CONTRACT_ESTABLISHED"
    assert contract["tensor_contract_rederived"] is True
    assert contract["input"]["in_channels"] == 6
    assert contract["input"]["kernel_points"] == 15
    assert contract["instance_head"]["head0_shape"] == [6, 48]
    assert contract["instance_head"]["head1_shape"] == [1, 48]
    assert contract["identify_head"]["out_channels"] == 7
    assert contract["output"]["instance_ids_generated_by_network"] is False
    assert contract["output"]["fdi_encoded"] is False
    assert contract["output"]["arch_encoded"] is False
    assert contract["output"]["left_right_encoded"] is False
    assert contract["label_names_stored_in_checkpoint"] is False
    assert contract["preprocessing_stored_in_checkpoint"] is False
    assert report["config_yaml"]["matches_seven_class_formula"] is False


def test_direct_contract_loader_rejects_a_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "absent.ckpt"
    contract = extract_checkpoint_contract(missing)
    assert contract["state"] == "MODEL_LOAD_FAILED"
    assert contract["tensor_contract_rederived"] is False


def test_host_runner_does_not_fake_inference_or_select_a_fixture() -> None:
    report = run_fv01_execution(hash_checkpoint=False, attempt_inference=True, stl_path=None)
    assert report["fixture_selected"] is False
    assert report["clinical_accuracy_claim"] is False
    assert report["clinical_accuracy"] == "NOT_ESTABLISHED"
    assert report["inference"]["attempted"] is False
    assert report["inference"]["succeeded"] is False
    assert report["performance"]["inference_ms"] is None
    assert report["cpu_fallback"]["implemented"] is False
    assert report["onnx"]["generated_this_phase"] is False
    assert report["onnx"]["is_toothinstancenet_substitute"] is False
    assert "ONNX_BACKEND_NOT_READY" in report["onnx"]["states"]
    if report["driver"]["nvidia_smi_present"] and not report["driver"]["visible"]:
        assert report["primary_state"] == "DRIVER_UNAVAILABLE"
        assert report["cpu_fallback"]["decision"] == "RULED_OUT"
        assert report["architecture_recommendation"] == "B"


def test_refused_inference_does_not_invent_fdi_or_confidence(tmp_path: Path) -> None:
    stl = tmp_path / "scan.stl"
    stl.write_bytes(b"solid scan\nendsolid scan\n")
    report = run_fv01_execution(hash_checkpoint=False, attempt_inference=True, stl_path=stl)
    assert report["inference"]["succeeded"] is False
    assert "fdi" not in report["inference"]
    assert "confidence" not in report["inference"]
    if not report["ready"]:
        assert report["primary_state"] != "INFERENCE_SUCCEEDED"
