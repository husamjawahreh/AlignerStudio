"""Importer gates for external CUDA segmentation evidence.

Payloads in this file are contract samples for the sealer. They are not an A100
forward pass, not observed anatomy, and not clinical truth.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import trimesh
from app.store import InMemoryCaseStore
from fastapi.testclient import TestClient

from domain.tooth.segmentation_review import SEMANTIC_IDENTITY_NOT_ESTABLISHED
from engines.geometry.intake_inspection import inspect_source_file
from engines.geometry.scan_preparation import accept_preparation, apply_operation
from engines.segmentation.fv03_1_runtime import PINNED_CHECKPOINT_SHA256
from engines.segmentation.fv03_2_evidence import (
    PREDICTION_PREPROCESSING_PIPELINE,
    PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE,
    canonical_raw_model_output,
    sha256_canonical,
)
from engines.segmentation.fv03_pipeline import (
    import_external_segmentation_evidence,
    reset_segmentation_jobs,
    review_segmentation,
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


def _instances() -> list[dict]:
    return [
        {
            "instance_id": "inst-0",
            "face_indices": [0, 1],
            "raw_model_class": 2,
            "confidence": 0.42,
            "confidence_available": True,
        },
        {
            "instance_id": "inst-1",
            "face_indices": [2, 3],
            "raw_model_class": 6,
            "confidence": None,
            "confidence_available": False,
        },
    ]


def _payload(artifact: dict, **overrides: object) -> dict:
    prepared = artifact["preparation"]["active"]["output_sha256"]
    instances = overrides.pop("instances", _instances())
    raw = {"instances": instances}
    body = {
        "run_id": "ext-run-1",
        "case_id": "case-1",
        "execution_origin": "EXTERNAL_CUDA",
        "execution_host": "colab-a100",
        "execution_device": "cuda:0",
        "gpu_model": "NVIDIA A100-SXM4-80GB",
        "python_version": "3.12",
        "pytorch_version": "2.11.0+cu128",
        "cuda_version": "12.8",
        "pointops_identity": "pointops-cuda-extension",
        "model_identifier": "instseg_full.ckpt",
        "checkpoint_sha256": PINNED_CHECKPOINT_SHA256,
        "claims_reference_checkpoint": True,
        "model_version": "3dteethland-424252e3d94a1565c8c2090eb5bb456b76386b93",
        "prepared_input_artifact_id": prepared,
        "prepared_input_sha256": prepared,
        "preprocessing": {
            "pipeline": list(PREDICTION_PREPROCESSING_PIPELINE),
            "rng_seed": 123456,
        },
        "rng_seed": 123456,
        "reproducibility_claimed": True,
        "inference_duration_ms": 12.5,
        "peak_gpu_memory_bytes": None,
        "raw_model_output": raw,
        "raw_output_sha256": sha256_canonical(canonical_raw_model_output(instances)),
        "instance_clustering": {"algorithm": "learned_region_cluster"},
        "verified": True,
    }
    body.update(overrides)
    return body


def test_valid_external_cuda_evidence_can_be_sealed(tmp_path: Path) -> None:
    path = tmp_path / "upper.stl"
    _box(path)
    artifact = _accepted(path)
    decision = import_external_segmentation_evidence(
        artifact, _payload(artifact), case_id="case-1"
    )
    assert decision["sealed"] is True
    assert decision["execution_origin"] == "EXTERNAL_CUDA"
    assert decision["native_execution"] is False
    assert decision["local_native"] is False
    assert decision["inference_executed_by_this_process"] is False
    assert decision["real_inference"] is True
    assert decision["review_state"] == "MODEL_PREDICTION"
    assert decision["clinically_verified"] is False
    assert decision["reproducibility_status"] == "REPRODUCIBLE"
    assert decision["ignored_client_verified"] is True
    run = artifact["segmentation"]["runs"][0]
    assert run["execution_origin"] == "EXTERNAL_CUDA"
    assert run["raw_model_output"]["instances"][0]["model_class_is_fdi"] is False
    assert artifact["segmentation"]["review"]["instances"][0]["review_state"] == "MODEL_PREDICTION"
    assert artifact["segmentation"]["review"]["instances"][0]["fdi"] is None


def test_incorrect_prepared_sha_prevents_sealing(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    payload = _payload(artifact, prepared_input_sha256="0" * 64)
    decision = import_external_segmentation_evidence(artifact, payload, case_id="case-1")
    assert decision["sealed"] is False
    assert "prepared_sha_mismatch" in decision["blockers"]
    assert decision["persisted"] is False
    assert not (artifact.get("segmentation") or {}).get("runs")


def test_incorrect_checkpoint_sha_prevents_sealing(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    payload = _payload(artifact, checkpoint_sha256="a" * 64, verified=True)
    decision = import_external_segmentation_evidence(artifact, payload, case_id="case-1")
    assert decision["sealed"] is False
    assert "checkpoint_sha_mismatch" in decision["blockers"]
    assert decision["real_inference"] is False


def test_missing_raw_output_prevents_sealing(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    payload = _payload(artifact)
    payload["raw_model_output"] = None
    decision = import_external_segmentation_evidence(artifact, payload, case_id="case-1")
    assert decision["sealed"] is False
    assert "raw_output_missing" in decision["blockers"]


def test_incorrect_raw_output_sha_prevents_sealing(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    payload = _payload(artifact, raw_output_sha256="b" * 64)
    decision = import_external_segmentation_evidence(artifact, payload, case_id="case-1")
    assert decision["sealed"] is False
    assert "raw_output_sha_mismatch" in decision["blockers"]


def test_invalid_geometry_prevents_sealing(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    instances = _instances()
    instances[0] = {**instances[0], "face_indices": [0, 999]}
    payload = _payload(artifact, instances=instances)
    decision = import_external_segmentation_evidence(artifact, payload, case_id="case-1")
    assert decision["sealed"] is False
    assert decision["validation_status"] == "INVALID"
    assert any("face_index" in item or "invalid_geometry" in item for item in decision["blockers"])
    assert decision["validation"]["repaired"] is False


def test_external_cuda_cannot_become_local_native(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    payload = _payload(artifact, local_native=True, native_execution=True)
    decision = import_external_segmentation_evidence(artifact, payload, case_id="case-1")
    assert decision["sealed"] is False
    assert decision["native_execution"] is False
    assert decision["local_native"] is False
    assert decision["execution_origin"] != "LOCAL_NATIVE"
    assert "external_import_cannot_become_local_native" in decision["blockers"]


def test_simulated_cannot_become_real_inference(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    payload = _payload(artifact, execution_origin="SIMULATED", real_inference=True)
    decision = import_external_segmentation_evidence(artifact, payload, case_id="case-1")
    assert decision["sealed"] is False
    assert decision["real_inference"] is False
    assert "simulated_is_not_real_inference" in decision["blockers"]


def test_unknown_origin_is_not_genuine_inference(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    payload = _payload(artifact, execution_origin="UNKNOWN", real_inference=True)
    decision = import_external_segmentation_evidence(artifact, payload, case_id="case-1")
    assert decision["sealed"] is False
    assert decision["real_inference"] is False
    assert "unknown_origin_is_not_genuine_inference" in decision["blockers"]


def test_model_class_cannot_become_fdi(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    decision = import_external_segmentation_evidence(
        artifact, _payload(artifact), case_id="case-1"
    )
    assert decision["sealed"] is True
    instance = artifact["segmentation"]["review"]["instances"][0]
    assert instance["raw_model_class"] == 2
    assert instance["fdi"] is None
    assert instance["model_class_mapping"] == SEMANTIC_IDENTITY_NOT_ESTABLISHED
    claimed = _payload(artifact)
    claimed["raw_model_output"]["instances"][0]["fdi"] = 11
    claimed["raw_output_sha256"] = sha256_canonical(
        canonical_raw_model_output(claimed["raw_model_output"]["instances"])
    )
    refused = import_external_segmentation_evidence(artifact, claimed, case_id="case-1")
    assert refused["sealed"] is False
    assert "fdi_present" in refused["blockers"]


def test_model_confidence_is_not_clinical_confidence(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    decision = import_external_segmentation_evidence(
        artifact, _payload(artifact), case_id="case-1"
    )
    summary = decision["evidence"]["confidence_summary"]
    assert summary["label"] == "model_confidence"
    assert summary["clinical_confidence"] == "NOT_ESTABLISHED"
    assert "clinical confidence" not in str(summary).lower() or summary["clinical_confidence"] == "NOT_ESTABLISHED"
    missing = artifact["segmentation"]["review"]["instances"][1]
    assert missing["confidence"] is None
    assert missing["confidence_available"] is False


def test_doctor_modification_preserves_model_prediction(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    import_external_segmentation_evidence(artifact, _payload(artifact), case_id="case-1")
    raw = copy.deepcopy(artifact["segmentation"]["runs"][0]["raw_model_output"])
    model_faces = [
        list(item["geometry_ref"]["face_indices"])
        for item in artifact["segmentation"]["review"]["model_instances"]
    ]
    review_segmentation(
        artifact,
        "merge",
        {"instance_id": "inst-0", "other_instance_id": "inst-1"},
    )
    assert artifact["segmentation"]["runs"][0]["raw_model_output"] == raw
    assert [
        list(item["geometry_ref"]["face_indices"])
        for item in artifact["segmentation"]["review"]["model_instances"]
    ] == model_faces
    assert artifact["segmentation"]["review"]["model_instances"][0]["review_state"] == "MODEL_PREDICTION"


def test_doctor_acceptance_does_not_become_clinical_verification(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    import_external_segmentation_evidence(artifact, _payload(artifact), case_id="case-1")
    review_segmentation(artifact, "accept", {"instance_id": "inst-0"})
    accepted = next(
        item
        for item in artifact["segmentation"]["review"]["instances"]
        if item["instance_id"] == "inst-0"
    )
    assert accepted["review_state"] == "DOCTOR_ACCEPTED"
    assert accepted["truth_state"] != "VERIFIED"
    assert artifact["segmentation"]["runs"][0]["clinically_verified"] is False
    assert artifact["segmentation"]["clinical_accuracy_claim"] is False


def test_evidence_hash_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    payload = _payload(artifact)
    first = import_external_segmentation_evidence(artifact, payload, case_id="case-1")
    second_artifact = _accepted(path)
    second = import_external_segmentation_evidence(second_artifact, payload, case_id="case-1")
    assert first["evidence_sha256"] == second["evidence_sha256"]
    assert first["evidence_intact"] is True
    assert second["evidence_intact"] is True


def test_preprocessing_evidence_file_is_unchanged(tmp_path: Path) -> None:
    evidence_path = Path(PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE)
    before = evidence_path.read_bytes()
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    import_external_segmentation_evidence(artifact, _payload(artifact), case_id="case-1")
    assert evidence_path.read_bytes() == before


def test_api_ignores_client_verified_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import app

    store = InMemoryCaseStore(tmp_path / "cases.json")
    monkeypatch.setattr("app.routers.cases.case_store", store)
    monkeypatch.setattr("app.segmentation_jobs.case_store", store)
    monkeypatch.setattr("app.preparation_jobs.case_store", store)
    monkeypatch.setattr("app.routers.cases.UPLOAD_DIR", tmp_path)
    client = TestClient(app)
    created = client.post("/cases", json={"patient_reference": "fv032-external"}).json()
    stl = tmp_path / "scan.stl"
    _box(stl)
    uploaded = client.post(
        f"/cases/{created['id']}/uploads",
        params={"arch": "upper"},
        files={"file": ("scan.stl", stl.read_bytes(), "model/stl")},
    )
    assert uploaded.status_code == 200
    prepared = client.post(
        f"/cases/{created['id']}/uploads/upper/preparation/apply",
        json={
            "operation": "orient",
            "parameters": {
                "method": "user_transform",
                "rotation_deg": [0, 0, 90],
                "translation": [0, 0, 0],
            },
        },
    )
    assert prepared.status_code == 200
    accepted = client.post(f"/cases/{created['id']}/uploads/upper/preparation/accept")
    assert accepted.status_code == 200
    case = client.get(f"/cases/{created['id']}").json()
    prepared_sha = case["intake_artifacts"][0]["preparation"]["active"]["output_sha256"]
    artifact = {"preparation": {"active": {"output_sha256": prepared_sha}}}
    payload = _payload(artifact)
    payload["case_id"] = created["id"]
    payload["verified"] = True
    payload["checkpoint_sha256"] = "c" * 64
    refused = client.post(
        f"/cases/{created['id']}/uploads/upper/segmentation/external-evidence",
        json=payload,
    )
    assert refused.status_code == 200
    body = refused.json()
    assert body["sealed"] is False
    assert "checkpoint_sha_mismatch" in body["blockers"]
    assert body["clinically_verified"] is False
    payload = _payload(artifact)
    payload["case_id"] = created["id"]
    sealed = client.post(
        f"/cases/{created['id']}/uploads/upper/segmentation/external-evidence",
        json=payload,
    )
    assert sealed.status_code == 200
    sealed_body = sealed.json()
    assert sealed_body["sealed"] is True
    assert sealed_body["execution_origin"] == "EXTERNAL_CUDA"
    assert sealed_body["native_execution"] is False
    assert sealed_body["inference_executed_by_this_process"] is False
