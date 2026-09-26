"""FV-03 segmentation input gate, blocked runtime, mock contract, and review edits.

The mock backend is a contract stand-in. It is not ToothInstanceNet inference.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import trimesh
from app.store import InMemoryCaseStore
from fastapi.testclient import TestClient

from domain.tooth.segmentation_review import CAPABILITY_STATES, SegmentationReviewError
from engines.geometry.intake_inspection import inspect_source_file
from engines.geometry.scan_preparation import accept_preparation, apply_operation
from engines.segmentation.fv03_pipeline import (
    DeterministicMockBackend,
    SegmentationInputError,
    SegmentationJobConflict,
    assess_segmentation_input,
    cancel_segmentation_job,
    detect_tin_capability,
    measure_segmentation_capability,
    reset_segmentation_jobs,
    review_segmentation,
    run_segmentation_job,
    submit_segmentation_job,
    wait_segmentation_job,
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


def test_segmentation_accepts_only_an_accepted_prepared_artifact(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    raw = inspect_source_file(
        path, case_id="case-1", explicit_arch="upper", original_filename="scan.stl"
    )
    refused = assess_segmentation_input(raw)
    assert refused["accepted"] is False
    assert "raw_unprepared_input" in refused["reasons"]
    with pytest.raises(SegmentationInputError):
        submit_segmentation_job(
            raw,
            case_id="case-1",
            arch="upper",
            backend=DeterministicMockBackend(),
            schedule=False,
        )
    prepared = _accepted(path)
    gate = assess_segmentation_input(prepared)
    assert gate["accepted"] is True
    assert gate["prepared_sha256"]
    assert gate["prepared_sha256"] != gate["source_sha256"]
    assert gate["clinically_ready"] is False


def test_stale_prepared_artifact_is_not_segmentation_input(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    artifact["preparation"]["active"]["output_sha256"] = "0" * 64
    gate = assess_segmentation_input(artifact)
    assert gate["accepted"] is False
    assert (
        "derived_hash_mismatch" in gate["reasons"]
        or "lineage_output_mismatch" in gate["reasons"]
    )


def test_mock_contract_is_not_real_inference_and_preserves_provenance(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    finished = _run_mock(artifact)
    assert finished["state"] == "completed"
    assert finished["real_inference"] is False
    assert finished["fixture"] is False
    assert finished["fdi_assigned"] is False
    assert finished["clinically_segmented"] is False
    assert finished["semantic_identity"] == "NOT_ESTABLISHED"
    assert finished["prepared_input_sha"] == artifact["preparation"]["active"]["output_sha256"]
    run = artifact["segmentation"]["active_run"]
    assert run["real_inference"] is False
    assert run["inference_kind"] == "mock_contract"
    assert run["reviewable"] is True
    assert run["semantic_identity"] == "NOT_ESTABLISHED"
    instances = artifact["segmentation"]["review"]["instances"]
    assert len(instances) == 2
    assert {item["raw_model_class"] for item in instances} == {0, 1}
    assert {item["model_class_mapping"] for item in instances} == {"NOT_ESTABLISHED"}
    assert all(item["fdi"] is None for item in instances)
    assert all(item["truth_state"] == "PREDICTED" for item in instances)
    assert all(item["review_state"] == "MODEL_PREDICTION" for item in instances)
    assert all(item["confidence"] is None for item in instances)
    assert artifact["segmentation"]["clinical_validation"] is False
    model = artifact["segmentation"]["review"]["model_instances"]
    assert [item["instance_id"] for item in model] == ["inst-0", "inst-1"]


def test_review_edits_do_not_rewrite_the_model_prediction(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    _run_mock(artifact)
    review_segmentation(artifact, "accept", {"instance_id": "inst-0"})
    accepted = next(
        item
        for item in artifact["segmentation"]["review"]["instances"]
        if item["instance_id"] == "inst-0"
    )
    assert accepted["review_state"] == "DOCTOR_ACCEPTED"
    assert accepted["truth_state"] != "VERIFIED"
    model = artifact["segmentation"]["review"]["model_instances"]
    assert model[0]["review_state"] == "MODEL_PREDICTION"
    review_segmentation(artifact, "reject", {"instance_id": "inst-1"})
    rejected = next(
        item
        for item in artifact["segmentation"]["review"]["instances"]
        if item["instance_id"] == "inst-1"
    )
    assert rejected["review_state"] == "DOCTOR_REJECTED"
    assert rejected["truth_state"] == "INVALID"
    review_segmentation(artifact, "undo", {})
    restored = next(
        item
        for item in artifact["segmentation"]["review"]["instances"]
        if item["instance_id"] == "inst-1"
    )
    assert restored["review_state"] == "MODEL_PREDICTION"
    review_segmentation(artifact, "reset", {})
    assert all(
        item["review_state"] == "MODEL_PREDICTION"
        for item in artifact["segmentation"]["review"]["instances"]
    )


def test_merge_and_split_require_a_real_partition(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    _run_mock(artifact)
    review_segmentation(
        artifact,
        "merge",
        {"instance_id": "inst-0", "other_instance_id": "inst-1"},
    )
    merged = artifact["segmentation"]["review"]["instances"]
    assert len(merged) == 1
    assert merged[0]["review_state"] == "DOCTOR_MODIFIED"
    assert merged[0]["truth_state"] == "PROPOSED"
    assert merged[0]["fdi"] is None
    assert artifact["segmentation"]["review"]["model_instances"][0]["truth_state"] == "PREDICTED"
    review_segmentation(artifact, "reset", {})
    with pytest.raises(SegmentationReviewError):
        review_segmentation(artifact, "split", {"instance_id": "inst-0", "face_indices": []})
    faces = artifact["segmentation"]["review"]["instances"][0]["geometry_ref"]["face_indices"]
    review_segmentation(artifact, "split", {"instance_id": "inst-0", "face_indices": faces[:1]})
    parts = artifact["segmentation"]["review"]["instances"]
    assert len(parts) == 3
    split_parts = [item for item in parts if item["instance_id"] != "inst-1"]
    assert all(item["review_state"] == "DOCTOR_MODIFIED" for item in split_parts)
    assert sum(item["geometry_ref"]["face_count"] for item in split_parts) == len(faces)


def test_stale_job_does_not_overwrite_a_newer_run(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    first = _run_mock(artifact)
    assert first["state"] == "completed"
    first_run = artifact["segmentation"]["active_run_id"]
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
    assert artifact["segmentation"]["active_run_id"] == first_run


def test_cancel_publishes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    queued = submit_segmentation_job(
        artifact,
        case_id="case-1",
        arch="upper",
        backend=DeterministicMockBackend(),
        schedule=False,
    )
    cancelled = cancel_segmentation_job(queued["job_id"])
    assert cancelled is not None
    assert cancelled["state"] == "cancelled"
    assert cancelled["output_run_id"] is None
    assert artifact["segmentation"].get("active_run_id") is None


def test_duplicate_job_reuses_the_active_request(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    backend = DeterministicMockBackend()
    first = submit_segmentation_job(
        artifact, case_id="case-1", arch="upper", backend=backend, schedule=False
    )
    second = submit_segmentation_job(
        artifact, case_id="case-1", arch="upper", backend=backend, schedule=False
    )
    assert second["duplicate"] is True
    assert second["job_id"] == first["job_id"]

    class _Other(DeterministicMockBackend):
        name = "other-mock"

    with pytest.raises(SegmentationJobConflict):
        submit_segmentation_job(
            artifact,
            case_id="case-1",
            arch="upper",
            backend=_Other(),
            schedule=False,
        )


def test_fixture_output_is_not_persisted(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)

    class _FixtureBackend(DeterministicMockBackend):
        name = "fixture_backend"

        def execute(self, prepared_path: Path, *, prepared_sha256: str) -> dict:
            produced = self.describe()
            return {
                "fixture": True,
                "status": "completed",
                "groups": [],
                "capability": produced,
            }

    queued = submit_segmentation_job(
        artifact, case_id="case-1", arch="upper", backend=_FixtureBackend(), schedule=False
    )
    finished = run_segmentation_job(queued["job_id"])
    assert finished is not None
    assert finished["state"] == "failed"
    assert finished["real_inference"] is False
    assert artifact["segmentation"].get("active_run_id") is None
    assert artifact["segmentation"].get("clinically_segmented") is not True


def test_tin_capability_does_not_fabricate_segmentation() -> None:
    capability = detect_tin_capability(refresh=True)
    assert capability["capability_state"] in CAPABILITY_STATES
    assert capability["fixture_selected"] is False
    assert capability["clinical_accuracy_claim"] is False
    assert capability["model_class_mapping"] == "NOT_ESTABLISHED"
    assert capability["fdi_encoded"] is False
    assert capability["real_inference"] is False
    if capability["executable"]:
        assert capability["capability_state"] == "AVAILABLE"
    else:
        assert capability["availability"] in {"ENVIRONMENT_BLOCKED", "NOT_AVAILABLE"}


def test_api_blocks_or_records_real_inference_without_fdi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import app

    store = InMemoryCaseStore(tmp_path / "cases.json")
    monkeypatch.setattr("app.routers.cases.case_store", store)
    monkeypatch.setattr("app.segmentation_jobs.case_store", store)
    monkeypatch.setattr("app.preparation_jobs.case_store", store)
    monkeypatch.setattr("app.routers.cases.UPLOAD_DIR", tmp_path)
    client = TestClient(app)
    created = client.post("/cases", json={"patient_reference": "fv03"}).json()
    stl = tmp_path / "scan.stl"
    _box(stl)
    uploaded = client.post(
        f"/cases/{created['id']}/uploads",
        params={"arch": "upper"},
        files={"file": ("scan.stl", stl.read_bytes(), "model/stl")},
    )
    assert uploaded.status_code == 200
    refused = client.post(f"/cases/{created['id']}/uploads/upper/segmentation/jobs")
    assert refused.status_code == 400
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
    started = client.post(f"/cases/{created['id']}/uploads/upper/segmentation/jobs")
    assert started.status_code == 200
    body = started.json()
    assert body["state"] in {"queued", "running"}
    finished = wait_segmentation_job(body["job_id"], timeout_s=60)
    case = client.get(f"/cases/{created['id']}").json()
    segmentation = case["intake_artifacts"][0]["segmentation"]
    assert segmentation["semantic_identity"] == "NOT_ESTABLISHED"
    assert segmentation["fdi_assigned"] is False
    assert segmentation["clinically_segmented"] is False
    assert segmentation["clinical_accuracy_claim"] is False
    if finished["state"] == "completed":
        assert finished["real_inference"] is True
    else:
        assert finished["blocked"] is True
        assert finished["real_inference"] is False
        assert finished["error"]["code"] in CAPABILITY_STATES
        assert segmentation["active_run"]["status"] == "blocked"
        assert segmentation["review"]["instances"] == []


def test_real_scan_capability_measurement() -> None:
    source = Path("data/benchmark/real-case/upper.stl")
    if not source.is_file() or source.stat().st_size != 8_557_034:
        pytest.skip("Real FV-02 STL is not available at the measured size.")
    report = measure_segmentation_capability(source, Path(".research/tmp/fv03_reliability"))
    Path(".research/tmp").mkdir(parents=True, exist_ok=True)
    Path(".research/tmp/fv03_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    assert report["file_size"] == 8_557_034
    assert report["source_sha256"] == (
        "60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48"
    )
    assert report["vertex_count"] == 513_417
    assert report["face_count"] == 171_139
    assert report["input_gate_accepted"] is True
    assert report["fdi_assigned"] is False
    assert report["clinically_segmented"] is False
    assert report["semantic_identity"] == "NOT_ESTABLISHED"
    assert report["fixture_selected"] is False
    assert report["capability_state"] in CAPABILITY_STATES
    if report["executable"]:
        assert report["inference_attempted"] is True
        assert report["inference_ms"] is not None
    else:
        assert report["inference_attempted"] is False
        assert report["inference_ms"] is None
        assert report["availability"] in {"ENVIRONMENT_BLOCKED", "NOT_AVAILABLE"}
