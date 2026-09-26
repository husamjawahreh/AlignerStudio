"""FV-03.1 runtime manifest, self-test, evidence seal, and review provenance.

The deterministic mock is named and is not ToothInstanceNet inference.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from domain.tooth.segmentation_review import SegmentationReviewError, manual_segmentation_contract
from engines.geometry.intake_inspection import inspect_source_file
from engines.geometry.scan_preparation import accept_preparation, apply_operation
from engines.segmentation.fv03_1_runtime import (
    PINNED_CHECKPOINT_SHA256,
    SELF_TEST_STATES,
    build_runtime_manifest,
    classify_self_test,
    environment_specification,
    evidence_intact,
    execute_named_mock_contract,
    quality_evaluation,
    run_backend_self_test,
    run_real_segmentation_command,
    seal_evidence_bundle,
)
from engines.segmentation.fv03_pipeline import (
    DeterministicMockBackend,
    reset_segmentation_jobs,
    review_segmentation,
    run_segmentation_job,
    submit_segmentation_job,
)


@pytest.fixture(autouse=True)
def _clear_jobs() -> None:
    reset_segmentation_jobs()
    yield
    reset_segmentation_jobs()


def _box(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trimesh.creation.box().export(path)


def _accepted(path: Path) -> dict:
    artifact = inspect_source_file(
        path, case_id="case-1", explicit_arch="upper", original_filename=path.name
    )
    apply_operation(
        artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 0, 90], "translation": [0, 0, 0]},
    )
    accept_preparation(artifact)
    return artifact


def _run_mock(artifact: dict) -> dict:
    queued = submit_segmentation_job(
        artifact,
        case_id="case-1",
        arch="upper",
        backend=DeterministicMockBackend(),
        schedule=False,
    )
    finished = run_segmentation_job(queued["job_id"])
    assert finished is not None
    return finished


def _unavailable(state: str) -> dict:
    return {
        "capability_state": state,
        "applicable_states": [state],
        "checkpoint_present": True,
        "checkpoint_hash_matches": True,
        "checkpoint_contract_state": "TENSOR_CONTRACT_ESTABLISHED",
        "executable": False,
    }


def test_runtime_manifest_keeps_unavailable_values_null() -> None:
    manifest = build_runtime_manifest(
        {
            "python": "3.12.3",
            "os": "Linux",
            "cpu": "test-cpu",
            "ram_bytes": 1024,
            "pytorch": {"available": False, "version": None, "cuda_version": None},
            "cuda": {"cuda_device": None, "gpu_name": "should-not-be-copied"},
            "driver": {"visible": False},
            "pointops": {"available": False, "version": None},
            "checkpoint": {"present": False, "path": None, "sha256": None},
            "contract": {},
            "primary_state": "DRIVER_UNAVAILABLE",
        },
        capability_state="DRIVER_UNAVAILABLE",
        probe_host=False,
    )
    assert manifest["python_version"] == "3.12.3"
    assert manifest["cpu"] == "test-cpu"
    assert manifest["ram_bytes"] == 1024
    assert manifest["gpu_vendor"] is None
    assert manifest["gpu_model"] is None
    assert manifest["driver_version"] is None
    assert manifest["cuda_version"] is None
    assert manifest["pytorch_version"] is None
    assert manifest["pytorch_available"] is False
    assert manifest["cuda_extension_available"] is False
    assert manifest["pointops_available"] is False
    assert manifest["checkpoint_filename"] is None
    assert manifest["checkpoint_sha256"] is None
    assert manifest["backend_package_versions"]["torch"] is None
    assert manifest["required_input_channels"] == 6
    assert manifest["required_model_outputs"]["fdi_encoded"] is False
    assert manifest["runtime_capability_state"] == "DRIVER_UNAVAILABLE"
    spec = environment_specification()
    assert spec["application_dependency"] is False
    assert spec["pytorch"]["mandatory_for_application_startup"] is False
    assert spec["expected_self_test_when_pins_match"] == "READY_FOR_INFERENCE"


@pytest.mark.parametrize(
    "state",
    ["DRIVER_UNAVAILABLE", "PYTORCH_UNAVAILABLE", "CUDA_EXTENSION_UNAVAILABLE"],
)
def test_unavailable_runtime_components_are_environment_blocked(state: str) -> None:
    classified = classify_self_test(_unavailable(state))
    assert classified["state"] == "ENVIRONMENT_UNAVAILABLE"
    assert state in classified["environment_blockers"]
    assert classified["entered_inference"] is False
    assert classified["real_inference"] is False
    assert classified["contract_metadata_valid"] is True


def test_invalid_model_contract_is_distinct_from_a_missing_runtime() -> None:
    classified = classify_self_test(
        {
            "capability_state": "MODEL_CONTRACT_UNAVAILABLE",
            "applicable_states": ["MODEL_CONTRACT_UNAVAILABLE"],
            "checkpoint_present": True,
            "checkpoint_hash_matches": True,
            "checkpoint_contract_state": "MODEL_CONTRACT_UNKNOWN",
            "executable": False,
        }
    )
    assert classified["state"] == "MODEL_CONTRACT_INVALID"
    assert classified["contract_metadata_valid"] is False
    assert classified["real_inference"] is False


def test_valid_contract_metadata_does_not_mean_ready() -> None:
    classified = classify_self_test(_unavailable("DRIVER_UNAVAILABLE"))
    assert classified["contract_metadata_valid"] is True
    assert classified["checkpoint_contract_state"] == "TENSOR_CONTRACT_ESTABLISHED"
    assert classified["state"] == "ENVIRONMENT_UNAVAILABLE"
    assert classified["state"] in SELF_TEST_STATES


def test_runtime_initialization_and_input_contract_are_distinct() -> None:
    ready = {
        "capability_state": "AVAILABLE",
        "applicable_states": ["AVAILABLE"],
        "checkpoint_present": True,
        "checkpoint_hash_matches": True,
        "checkpoint_contract_state": "TENSOR_CONTRACT_ESTABLISHED",
        "executable": True,
    }
    failed = classify_self_test(ready, init_error="model init failed")
    assert failed["state"] == "RUNTIME_INITIALIZATION_FAILED"
    invalid_input = classify_self_test(ready, input_gate={"accepted": False, "reasons": ["finite"]})
    assert invalid_input["state"] == "INPUT_CONTRACT_INVALID"
    prepared = classify_self_test(ready)
    assert prepared["state"] == "READY_FOR_INFERENCE"
    assert prepared["real_inference"] is False
    assert prepared["entered_inference"] is False


def test_blocked_inference_gate_does_not_enter_inference() -> None:
    from engines.segmentation.fv03_1_runtime import evaluate_inference_gates

    decision = evaluate_inference_gates(
        self_test={"state": "ENVIRONMENT_UNAVAILABLE"},
        input_gate={"accepted": True},
        model_sha256=PINNED_CHECKPOINT_SHA256,
        input_sha256="abc",
        expected_input_sha256="abc",
        contract_valid=True,
        capability_executable=False,
    )
    assert decision["passed"] is False
    assert decision["entered_inference"] is False
    assert decision["real_inference"] is False
    assert decision["clinically_verified"] is False
    assert decision["primary_blocker"] == "ENVIRONMENT_UNAVAILABLE"


def test_live_self_test_does_not_fabricate_inference() -> None:
    probed = run_backend_self_test()
    assert probed["entered_inference"] is False
    assert probed["real_inference"] is False
    assert probed["clinically_verified"] is False
    assert probed["fixture_selected"] is False
    assert probed["self_test"]["state"] in SELF_TEST_STATES
    assert probed["quality_evaluation"]["quality_evaluation"] == "NOT_AVAILABLE"
    assert probed["quality_evaluation"]["dice"] is None
    manifest = probed["runtime_manifest"]
    if not manifest.get("pytorch_available"):
        assert manifest.get("pytorch_version") is None
    if not manifest.get("cuda_extension_available"):
        assert manifest.get("pointops_version") is None
    if not manifest.get("checkpoint_present"):
        assert manifest.get("checkpoint_sha256") is None
    elif manifest.get("checkpoint_sha256"):
        assert manifest["checkpoint_sha256"] == PINNED_CHECKPOINT_SHA256 or (
            probed["self_test"]["state"] == "MODEL_UNAVAILABLE"
        )
    assert probed["manual_segmentation"]["status"] == "NOT_IMPLEMENTED"
    assert probed["manual_segmentation"]["substitutes_model_prediction"] is False


def test_real_command_stores_the_blocker_without_inference(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    result = run_real_segmentation_command(artifact, case_id="case-1")
    assert result["real_inference"] is False
    assert result["clinically_verified"] is False
    if result["self_test"]["state"] != "READY_FOR_INFERENCE":
        assert result["entered_inference"] is False
        assert result["primary_blocker"]
        assert result["blocker"]["message"] == "Inference was not entered."
    else:
        assert result["entered_inference"] is True
        assert result["clinically_verified"] is False


def test_mock_execution_contract_is_named_and_not_real_inference(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    blocked = execute_named_mock_contract(artifact, self_test_state="ENVIRONMENT_UNAVAILABLE")
    assert blocked["entered_inference"] is False
    assert blocked["real_inference"] is False
    assert blocked["backend_name"] == "deterministic_mock"
    executed = execute_named_mock_contract(artifact, self_test_state="READY_FOR_INFERENCE")
    assert executed["entered_inference"] is True
    assert executed["real_inference"] is False
    assert executed["inference_kind"] == "mock_contract"
    assert executed["backend_name"] == "deterministic_mock"
    assert executed["clinically_verified"] is False
    assert executed["instance_count"] == 2


def test_evidence_bundle_is_immutable_after_review(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    _run_mock(artifact)
    run = artifact["segmentation"]["runs"][0]
    evidence = run["evidence"]
    assert evidence["immutable"] is True
    assert evidence["real_inference"] is False
    assert evidence["inference_duration_ms"] is None
    assert evidence["clinically_verified"] is False
    assert evidence["quality_evaluation"]["quality_evaluation"] == "NOT_AVAILABLE"
    assert evidence_intact(evidence)
    tampered = {**evidence, "inference_duration_ms": 12.0}
    assert evidence_intact(tampered) is False
    review_segmentation(
        artifact,
        "merge",
        {"instance_id": "inst-0", "other_instance_id": "inst-1"},
    )
    assert evidence_intact(run["evidence"])
    assert run["evidence"]["evidence_sha256"] == evidence["evidence_sha256"]
    assert artifact["segmentation"]["review"]["model_instances"][0]["review_state"] == (
        "MODEL_PREDICTION"
    )
    sealed = seal_evidence_bundle({"run_id": "x", "real_inference": False})
    assert evidence_intact(sealed)


def test_review_provenance_records_merge_and_refuses_split(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    _run_mock(artifact)
    model_faces = [
        list(item["geometry_ref"]["face_indices"])
        for item in artifact["segmentation"]["review"]["model_instances"]
    ]
    review_segmentation(artifact, "accept", {"instance_id": "inst-0"})
    review_segmentation(artifact, "undo", {})
    review_segmentation(artifact, "redo", {})
    accepted = next(
        item
        for item in artifact["segmentation"]["review"]["instances"]
        if item["instance_id"] == "inst-0"
    )
    assert accepted["review_state"] == "DOCTOR_ACCEPTED"
    review_segmentation(artifact, "reset", {})
    review_segmentation(
        artifact,
        "merge",
        {"instance_id": "inst-0", "other_instance_id": "inst-1"},
    )
    merge = next(
        item
        for item in artifact["segmentation"]["review"]["events"]
        if item.get("operation") == "merge"
    )
    assert merge["previous_segmentation_state"]
    assert merge["affected_instance_ids"] == [
        "inst-0",
        "inst-1",
        merge["parameters"]["instance_id"],
    ]
    assert merge["parameters"]["operation"] == "merge"
    assert merge["timestamp"]
    assert merge["resulting_geometry_hash"]
    assert merge["mutates_model_prediction"] is False
    assert [
        list(item["geometry_ref"]["face_indices"])
        for item in artifact["segmentation"]["review"]["model_instances"]
    ] == model_faces
    with pytest.raises(SegmentationReviewError, match="SPLIT_UNAVAILABLE"):
        review_segmentation(artifact, "split", {"instance_id": "inst-0", "face_indices": [0]})
    assert artifact["segmentation"]["review"]["model_instances"][0]["truth_state"] == "PREDICTED"
    contract = manual_segmentation_contract()
    assert contract["status"] == "NOT_IMPLEMENTED"
    assert "MODEL_PREDICTION" in contract["distinct_from"]
    assert contract["clinical_verification"] is False


def test_quality_evaluation_is_not_available_without_ground_truth() -> None:
    report = quality_evaluation(ground_truth_present=False, measurements={"dice": 0.99})
    assert report["quality_evaluation"] == "NOT_AVAILABLE"
    assert report["dice"] is None
    assert report["iou"] is None
    assert report["hausdorff_distance"] is None
    assert report["clinical_accuracy"] == "NOT_ESTABLISHED"
    recorded = quality_evaluation(ground_truth_present=True, measurements={"dice": 0.5})
    assert recorded["quality_evaluation"] == "RECORDED"
    assert recorded["dice"] == 0.5
    assert recorded["iou"] is None
    assert recorded["clinical_accuracy"] == "NOT_ESTABLISHED"


def test_stale_run_keeps_the_sealed_evidence(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    first = _run_mock(artifact)
    assert first["state"] == "completed"
    evidence = artifact["segmentation"]["runs"][0]["evidence"]
    digest = evidence["evidence_sha256"]
    active = artifact["segmentation"]["active_run_id"]
    queued = submit_segmentation_job(
        artifact,
        case_id="case-1",
        arch="upper",
        backend=DeterministicMockBackend(),
        schedule=False,
    )
    artifact["segmentation"]["generation"] = int(artifact["segmentation"]["generation"]) + 1
    finished = run_segmentation_job(queued["job_id"])
    assert finished is not None
    assert finished["state"] == "failed"
    assert finished["error"]["code"] == "STALE_SEGMENTATION"
    assert artifact["segmentation"]["active_run_id"] == active
    assert artifact["segmentation"]["runs"][0]["evidence"]["evidence_sha256"] == digest
    assert evidence_intact(artifact["segmentation"]["runs"][0]["evidence"])
