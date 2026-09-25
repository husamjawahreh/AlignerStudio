"""WP-01 — Real Clinical Data Pipeline: no silent fixture substitution."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline_diagnostics import PipelineState, process_uploaded_case
from app.processing import compute_case_input_hash, start_processing
from app.processing_modes import ProcessingMode, ProcessingModeError, resolve_processing_mode
from app.segmentation_store import (
    begin_segmentation_record,
    complete_segmentation_record,
    get_segmentation_record,
    store_arch_result,
)
from app.store import case_store
from app.treatment_sessions import treatment_sessions
from domain.case.models import Case, MeshAsset
from domain.tooth.identification import ArchType


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".research" / "tmp" / "official_real_case_stage2_verified_v1"
ARTIFACT_ZIP = ROOT / "official_real_case_stage2_verified_v1.zip"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear(tmp_path, monkeypatch):
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", raising=False)
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", raising=False)
    case_store.clear()
    treatment_sessions.clear()
    yield
    case_store.clear()
    treatment_sessions.clear()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_fixture_backend_blocked_without_allow_flag(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    with pytest.raises(ProcessingModeError, match="blocked for production"):
        resolve_processing_mode()


def test_fixture_backend_allowed_only_with_explicit_flag(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
    assert resolve_processing_mode() is ProcessingMode.TEST_FIXTURE


def test_production_process_uploaded_case_does_not_load_fixture(monkeypatch, tmp_path) -> None:
    """Real path must call ToothInstanceNet with the uploaded path — never fixture loader."""
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet")
    uploaded = tmp_path / "patient_upper.stl"
    uploaded.write_bytes(b"solid patient\nendsolid patient\n")
    called: dict = {}

    class FakeEngine:
        def segment(self, mesh_file_path: str):
            called["path"] = mesh_file_path
            raise RuntimeError("forced-inference-failure-for-path-check")

    monkeypatch.setattr(
        "app.real_case_pipeline.load_toothinstancenet_engine",
        lambda arch: FakeEngine(),
    )
    fixture_calls: list = []
    monkeypatch.setattr(
        "app.pipeline_diagnostics.load_validated_fixture_result",
        lambda *args, **kwargs: fixture_calls.append((args, kwargs))
        or (_ for _ in ()).throw(AssertionError("fixture")),
    )

    diagnostic = process_uploaded_case(
        str(uploaded), ArchType.UPPER, case_id="c1", job_id="j1", input_hash="h1"
    )
    assert called["path"] == str(uploaded)
    assert fixture_calls == []
    assert diagnostic.fixture is False
    assert diagnostic.processing_mode == ProcessingMode.REAL_CASE.value
    assert diagnostic.source_mesh_sha256 == _sha256(uploaded)
    assert diagnostic.state is PipelineState.SEGMENTATION_FAILED


def test_fixture_path_cannot_execute_for_production_real_case(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    uploaded = tmp_path / "upper.stl"
    uploaded.write_bytes(b"solid x\nendsolid x\n")
    diagnostic = process_uploaded_case(str(uploaded), ArchType.UPPER)
    assert diagnostic.state is PipelineState.MODEL_UNAVAILABLE
    assert diagnostic.fixture is False
    assert any("blocked" in failure.lower() or "fixture" in failure.lower() for failure in diagnostic.failures)


@pytest.mark.skipif(not ARTIFACT_DIR.is_dir(), reason="Need extracted artifact STLs")
def test_real_upload_hash_reaches_processing_and_record(tmp_path) -> None:
    case_id = client.post("/cases", json={"patient_reference": "wp01-hash"}).json()["id"]
    upper_src = ARTIFACT_DIR / "upper.stl"
    lower_src = ARTIFACT_DIR / "lower.stl"
    upper = tmp_path / "upper.stl"
    lower = tmp_path / "lower.stl"
    upper.write_bytes(upper_src.read_bytes())
    lower.write_bytes(lower_src.read_bytes())
    case = case_store.get(case_id)
    assert case is not None
    case.meshes = [
        MeshAsset("upper", str(upper), "upper.stl"),
        MeshAsset("lower", str(lower), "lower.stl"),
    ]
    case_store.update(case)
    input_hash = compute_case_input_hash(case_id)
    assert len(input_hash) == 64
    begin_segmentation_record(
        case_id,
        job_id="job-wp01",
        input_hash=input_hash,
        processing_mode=ProcessingMode.REAL_CASE.value,
    )
    store_arch_result(
        case_id,
        "upper",
        {
            "state": "identification_incomplete",
            "source_kind": "uploaded_real_case",
            "tooth_instances": [],
            "source_mesh_path": str(upper),
            "source_mesh_sha256": _sha256(upper),
            "fixture": False,
        },
        model_name="toothinstancenet",
        model_version="test",
    )
    complete_segmentation_record(case_id, status="completed")
    record = get_segmentation_record(case_id)
    assert record is not None
    assert record["job_id"] == "job-wp01"
    assert record["input_hash"] == input_hash
    assert record["processing_mode"] == ProcessingMode.REAL_CASE.value
    assert record["arches"]["upper"]["source_mesh_sha256"] == _sha256(upper)
    assert record["arches"]["upper"]["fixture"] is False


def test_real_failure_does_not_become_fixture_success(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet")
    uploaded = tmp_path / "upper.stl"
    uploaded.write_bytes(b"solid fail\nendsolid fail\n")

    class FakeEngine:
        def segment(self, mesh_file_path: str):
            raise RuntimeError("cuda/kernel unavailable")

    monkeypatch.setattr(
        "app.real_case_pipeline.load_toothinstancenet_engine",
        lambda arch: FakeEngine(),
    )
    monkeypatch.setattr(
        "app.pipeline_diagnostics.load_validated_fixture_result",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("fixture must not run")),
    )
    diagnostic = process_uploaded_case(str(uploaded), ArchType.UPPER)
    assert diagnostic.state is PipelineState.SEGMENTATION_FAILED
    assert diagnostic.fixture is False
    assert diagnostic.tooth_instance_count == 0


def test_job_identity_and_model_provenance_preserved(tmp_path) -> None:
    case = Case(patient_reference="prov")
    case_store.add(case)
    upper = tmp_path / "u.stl"
    lower = tmp_path / "l.stl"
    upper.write_bytes(b"u")
    lower.write_bytes(b"l")
    case.meshes = [
        MeshAsset("upper", str(upper), "u.stl"),
        MeshAsset("lower", str(lower), "l.stl"),
    ]
    case_store.update(case)
    input_hash = compute_case_input_hash(case.id)
    begin_segmentation_record(
        case.id, job_id="job-identity", input_hash=input_hash, processing_mode="real_case"
    )
    store_arch_result(
        case.id,
        "upper",
        {"state": "identification_incomplete", "tooth_instances": [], "fixture": False},
        model_name="toothinstancenet",
        model_version="instseg_full",
    )
    store_arch_result(
        case.id,
        "lower",
        {"state": "identification_incomplete", "tooth_instances": [], "fixture": False},
        model_name="toothinstancenet",
        model_version="instseg_full",
    )
    complete_segmentation_record(case.id, status="completed")
    record = get_segmentation_record(case.id)
    assert record["job_id"] == "job-identity"
    assert record["model_name"] == "toothinstancenet"
    assert record["model_version"] == "instseg_full"
    assert record["input_hash"] == input_hash


def test_no_fdi_fabricated_in_reconstruction() -> None:
    from app.plan_from_pipeline import _reconstruct_tooth

    tooth = _reconstruct_tooth(
        {
            "instance_id": 0,
            "fdi_number": None,
            "tooth_ref": "upper:instance:0",
            "semantic_label": 11,
            "arch": "upper",
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "faces": [[0, 1, 2]],
            "centroid": [0.3, 0.3, 0],
            "confidence": 0.0,
            "identification_status": "uncertain",
            "provenance": "experimental",
            "fixture": False,
        }
    )
    assert tooth.identity is None
    assert tooth.semantic_label == 11
    assert tooth.tooth_ref == "upper:instance:0"


@pytest.mark.skipif(not ARTIFACT_DIR.is_dir(), reason="extracted artifact required")
def test_fixture_hash_binding_rejects_unrelated_upload(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(ARTIFACT_DIR))
    unrelated = tmp_path / "random.stl"
    unrelated.write_bytes(b"solid random\nendsolid random\n")
    from adapters.toothinstancenet.fixture import ToothInstanceNetFixtureError, load_validated_fixture

    with pytest.raises(ToothInstanceNetFixtureError, match="does not match verified artifact"):
        load_validated_fixture(ARTIFACT_DIR, arch=ArchType.UPPER, source_mesh_path=unrelated)


@pytest.mark.skipif(not ARTIFACT_DIR.is_dir(), reason="extracted artifact required")
def test_fixture_hash_binding_accepts_matching_upload(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(ARTIFACT_DIR))
    from adapters.toothinstancenet.fixture import load_validated_fixture

    result = load_validated_fixture(
        ARTIFACT_DIR, arch=ArchType.UPPER, source_mesh_path=ARTIFACT_DIR / "upper.stl"
    )
    assert result.segmentation.metadata.fixture is True
    assert all(tooth.identity is None for tooth in result.identification.teeth)


def test_new_processing_job_gets_new_identity_after_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet")
    case_id = client.post("/cases", json={"patient_reference": "retry"}).json()["id"]
    upper = tmp_path / "upper.stl"
    lower = tmp_path / "lower.stl"
    upper.write_bytes(b"u")
    lower.write_bytes(b"l")
    case = case_store.get(case_id)
    assert case is not None
    case.meshes = [
        MeshAsset("upper", str(upper), "upper.stl"),
        MeshAsset("lower", str(lower), "lower.stl"),
    ]
    case_store.update(case)
    case_store.set_processing(
        case_id,
        {
            "job_id": "old-failed",
            "case_id": case_id,
            "stage_status": "FAILED",
            "current_stage": "SEGMENTING_BOTH",
            "overall_progress": 40,
            "started_at": "2026-01-01T00:00:00+00:00",
            "created_at": "2026-01-01T00:00:00+00:00",
            "input_hash": "abc",
            "completed_stages": [],
            "pending_stages": [],
            "error_state": True,
            "error_code": "PROCESSING_FAILED",
            "user_message": "failed",
        },
    )
    restarted = start_processing(case_id)
    assert restarted["job_id"] != "old-failed"
    assert restarted["overall_progress"] == 0
    assert restarted["current_stage"] == "PREPARING"
