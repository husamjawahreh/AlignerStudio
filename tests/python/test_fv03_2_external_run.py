"""Contract tests for the external inference runner.

Instances here are sealer contract samples. They are not an A100 forward pass.
"""

from __future__ import annotations

from pathlib import Path

import trimesh

from engines.geometry.intake_inspection import inspect_source_file
from engines.geometry.scan_preparation import accept_preparation, apply_operation
from engines.segmentation.fv03_1_runtime import PINNED_CHECKPOINT_SHA256
from engines.segmentation.fv03_2_evidence import sha256_canonical
from engines.segmentation.fv03_2_external_run import (
    FORBIDDEN_PREPROCESSING_SUBSTITUTE,
    OFFICIAL_PREPROCESSING,
    build_external_import_payload,
    external_run_status,
    run_external_inference,
    write_blocked_bundle,
)
from engines.segmentation.fv03_pipeline import (
    import_external_segmentation_evidence,
    reset_segmentation_jobs,
    review_segmentation,
)

import pytest


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


def _runtime() -> dict:
    return {
        "execution_host": "colab-protocol",
        "execution_device": "cuda:0",
        "gpu_model": "NVIDIA A100-SXM4-80GB",
        "python_version": "3.12",
        "pytorch_version": "2.11.0+cu128",
        "cuda_version": "12.8",
        "pointops_identity": "pointops-cuda-extension",
    }


def _instances() -> list[dict]:
    return [
        {
            "instance_id": "inst-0",
            "face_indices": [0, 1],
            "raw_model_class": 1,
            "confidence": 0.2,
            "confidence_available": True,
        },
        {
            "instance_id": "inst-1",
            "face_indices": [2, 3],
            "raw_model_class": 4,
            "confidence": None,
            "confidence_available": False,
        },
    ]


def _payload(artifact: dict, **overrides: object) -> dict:
    prepared = artifact["preparation"]["active"]["output_sha256"]
    payload = build_external_import_payload(
        run_id="ext-protocol-1",
        case_id="case-1",
        arch="upper",
        prepared_input_sha256=str(prepared),
        checkpoint_sha256=PINNED_CHECKPOINT_SHA256,
        runtime=_runtime(),
        rng_seed=123456,
        reproducibility_claimed=True,
        raw_instances=_instances(),
        inference_duration_ms=1.0,
    )
    payload.update(overrides)
    return payload


def test_runner_status_is_ready_but_inference_is_not_completed() -> None:
    status = external_run_status()
    assert status["READY_FOR_EXTERNAL_INFERENCE_RUN"] is True
    assert status["GENUINE_EXTERNAL_INFERENCE_COMPLETED"] is False
    assert status["preprocessing_implementation"] == OFFICIAL_PREPROCESSING
    assert status["preprocessing_forbidden_substitute"] == FORBIDDEN_PREPROCESSING_SUBSTITUTE
    assert status["prediction_pipeline"][0] == "ZScoreNormalize(norm=True)"
    assert status["prediction_pipeline"][-1] == "ToTensor"
    assert status["seed_is_universal_default"] is False
    assert status["documented_reproducibility_seed"] == 123456
    assert status["inference_determinism"] == "NOT_CLAIMED"
    assert status["fdi_mapping"] == "NOT_ESTABLISHED"


def test_protocol_without_execute_does_not_infer(tmp_path: Path) -> None:
    status = run_external_inference(
        prepared_mesh=tmp_path / "missing.stl",
        case_id="case-1",
        arch="upper",
        output_dir=tmp_path / "bundle",
        seed=123456,
        execute=False,
    )
    assert status["GENUINE_EXTERNAL_INFERENCE_COMPLETED"] is False
    assert status["executed"] is False
    assert not (tmp_path / "bundle" / "raw_output" / "instances.json").exists()


def test_execute_without_checkpoint_does_not_fabricate_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT", raising=False)
    monkeypatch.delenv("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE", raising=False)
    mesh = tmp_path / "upper.stl"
    _box(mesh)
    status = run_external_inference(
        prepared_mesh=mesh,
        case_id="case-1",
        arch="upper",
        output_dir=tmp_path / "bundle",
        seed=123456,
        execute=True,
    )
    assert status["GENUINE_EXTERNAL_INFERENCE_COMPLETED"] is False
    assert status["sealable_candidate"] is False
    assert not (tmp_path / "bundle" / "raw_output" / "instances.json").exists()
    assert any("checkpoint_unavailable" in item or item.endswith("_missing") for item in status["blockers"])


def test_required_runtime_metadata_checkpoint_seed_and_raw_sha(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    missing_gpu = _payload(artifact)
    missing_gpu["gpu_model"] = None
    refused_gpu = import_external_segmentation_evidence(artifact, missing_gpu, case_id="case-1")
    assert refused_gpu["sealed"] is False
    assert "gpu_model_missing" in refused_gpu["blockers"]

    missing_checkpoint = _payload(artifact, checkpoint_sha256=None)
    refused_checkpoint = import_external_segmentation_evidence(
        artifact, missing_checkpoint, case_id="case-1"
    )
    assert "checkpoint_sha_missing" in refused_checkpoint["blockers"]

    wrong_prepared = _payload(artifact, prepared_input_sha256="0" * 64)
    refused_prepared = import_external_segmentation_evidence(
        artifact, wrong_prepared, case_id="case-1"
    )
    assert "prepared_sha_mismatch" in refused_prepared["blockers"]

    bad_raw = _payload(artifact, raw_output_sha256="b" * 64)
    refused_raw = import_external_segmentation_evidence(artifact, bad_raw, case_id="case-1")
    assert "raw_output_sha_mismatch" in refused_raw["blockers"]

    missing_seed = _payload(artifact, rng_seed=None, reproducibility_claimed=True)
    missing_seed["preprocessing"] = {**missing_seed["preprocessing"], "rng_seed": None}
    refused_seed = import_external_segmentation_evidence(artifact, missing_seed, case_id="case-1")
    assert "reproducibility_seed_missing" in refused_seed["blockers"]


def test_origin_seed_hash_geometry_and_semantics(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    first = _payload(artifact)
    second = _payload(artifact)
    second["created_at"] = "2099-01-01T00:00:00+00:00"
    sealed_a = import_external_segmentation_evidence(artifact, first, case_id="case-1")
    other = _accepted(path)
    sealed_b = import_external_segmentation_evidence(other, second, case_id="case-1")
    assert sealed_a["sealed"] is True
    assert sealed_a["execution_origin"] == "EXTERNAL_CUDA"
    assert sealed_a["native_execution"] is False
    assert sealed_a["evidence_sha256"] == sealed_b["evidence_sha256"]
    assert sha256_canonical(first) != sha256_canonical(second)
    raw = artifact["segmentation"]["runs"][0]["raw_model_output"]
    review_segmentation(artifact, "accept", {"instance_id": "inst-0"})
    assert artifact["segmentation"]["runs"][0]["raw_model_output"] == raw
    accepted = artifact["segmentation"]["review"]["instances"][0]
    assert accepted["review_state"] == "DOCTOR_ACCEPTED"
    assert accepted["truth_state"] != "VERIFIED"
    assert accepted["fdi"] is None
    assert accepted["raw_model_class"] == 1
    assert sealed_a["evidence"]["confidence_summary"]["clinical_confidence"] == "NOT_ESTABLISHED"

    local = _payload(artifact, local_native=True)
    refused_local = import_external_segmentation_evidence(other, local, case_id="case-1")
    assert refused_local["sealed"] is False
    assert refused_local["execution_origin"] != "LOCAL_NATIVE"

    simulated = _payload(artifact, execution_origin="SIMULATED", real_inference=True)
    refused_sim = import_external_segmentation_evidence(other, simulated, case_id="case-1")
    assert refused_sim["real_inference"] is False

    unknown = _payload(artifact, execution_origin="UNKNOWN", real_inference=True)
    refused_unknown = import_external_segmentation_evidence(other, unknown, case_id="case-1")
    assert refused_unknown["real_inference"] is False

    invalid = _payload(artifact)
    invalid["raw_model_output"]["instances"][0]["face_indices"] = [0, 999]
    invalid["raw_output_sha256"] = sealed_a["evidence"]["raw_output_sha256"]
    from engines.segmentation.fv03_2_evidence import canonical_raw_model_output

    invalid["raw_output_sha256"] = sha256_canonical(
        canonical_raw_model_output(invalid["raw_model_output"]["instances"])
    )
    refused_geometry = import_external_segmentation_evidence(other, invalid, case_id="case-1")
    assert refused_geometry["sealed"] is False
    assert refused_geometry["validation_status"] == "INVALID"

    claimed = _payload(artifact, verified=True)
    claimed["raw_model_output"]["instances"][0]["fdi"] = 11
    claimed["raw_output_sha256"] = sha256_canonical(
        canonical_raw_model_output(claimed["raw_model_output"]["instances"])
    )
    refused_fdi = import_external_segmentation_evidence(other, claimed, case_id="case-1")
    assert refused_fdi["sealed"] is False
    assert refused_fdi["ignored_client_verified"] is True
    assert "fdi_present" in refused_fdi["blockers"]


def test_blocked_bundle_writer_does_not_invent_instances(tmp_path: Path) -> None:
    status = write_blocked_bundle(tmp_path / "blocked", blockers=["checkpoint_sha_missing"], detail={})
    assert status["GENUINE_EXTERNAL_INFERENCE_COMPLETED"] is False
    assert not (tmp_path / "blocked" / "raw_output" / "instances.json").exists()
