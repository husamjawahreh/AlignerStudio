"""Wave 1 — REAL_CASE segmentation recovery. No fixture substitution."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from app.main import app
from app.pipeline_diagnostics import PipelineState, process_uploaded_case
from app.processing import SEGMENTATION_FAILURE_STATES, cancel_processing, compute_case_input_hash
from app.processing_modes import (
    ProcessingMode,
    ProcessingModeError,
    resolve_processing_mode,
    selected_backend,
)
from app.segmentation_runtime import assess_segmentation_runtime
from app.segmentation_store import (
    begin_segmentation_record,
    complete_segmentation_record,
    get_segmentation_record,
    store_arch_result,
)
from app.store import InMemoryCaseStore, case_store
from app.treatment_sessions import treatment_sessions
from fastapi.testclient import TestClient

from domain.case.models import Case, MeshAsset
from domain.tooth.identification import ArchType

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / ".research" / "tmp" / "official_real_case_stage2_verified_v1"
LOWER_SHA = "5cb38bd65cb2a9f04c89c580774e2d6c4ed28582fb46cc160fdc1249020feec3"
UPPER_SHA = "96e23a65e6a0eaa5550704be628dd3d27c6c5813213f6ea6b48b386d5178bd1e"
client = TestClient(app)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.fixture(autouse=True)
def _clear(tmp_path, monkeypatch):
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", raising=False)
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", raising=False)
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_MODEL", raising=False)
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_CONTRACT", raising=False)
    monkeypatch.delenv("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT", raising=False)
    monkeypatch.delenv("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE", raising=False)
    case_store.clear()
    treatment_sessions.clear()
    yield
    case_store.clear()
    treatment_sessions.clear()


def test_real_case_never_selects_fixture_implicitly(monkeypatch) -> None:
    monkeypatch.delenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", raising=False)
    assert selected_backend() == "onnx"
    assert resolve_processing_mode() is ProcessingMode.REAL_CASE
    assessment = assess_segmentation_runtime()
    assert assessment["fixture_selected"] is False
    assert assessment["processing_mode"] == "real_case"
    assert assessment["backend"] == "onnx"


def test_test_fixture_stays_explicit(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    with pytest.raises(ProcessingModeError, match="blocked for production"):
        resolve_processing_mode()
    monkeypatch.setenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
    assert resolve_processing_mode() is ProcessingMode.TEST_FIXTURE


def test_backend_selection_is_deterministic(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet")
    assert selected_backend() == "toothinstancenet"
    assert resolve_processing_mode() is ProcessingMode.REAL_CASE
    assert assess_segmentation_runtime()["backend"] == "toothinstancenet"
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "onnx")
    assert selected_backend() == "onnx"
    assert resolve_processing_mode() is ProcessingMode.REAL_CASE


def test_missing_toothinstancenet_runtime_is_explicit(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet")
    uploaded = tmp_path / "lower.stl"
    uploaded.write_bytes(b"solid patient\nendsolid patient\n")
    before = _sha256(uploaded)
    diagnostic = process_uploaded_case(
        str(uploaded), ArchType.LOWER, case_id="c-wave1", job_id="j-wave1", input_hash="abc"
    )
    assert _sha256(uploaded) == before
    assert diagnostic.state is PipelineState.BLOCKED_BY_ENVIRONMENT
    assert diagnostic.segmentation_truth_state == "blocked_by_environment"
    assert diagnostic.fixture is False
    assert diagnostic.processing_mode == "real_case"
    assert diagnostic.backend == "toothinstancenet"
    assert diagnostic.tooth_instance_count == 0
    assert diagnostic.tooth_instances == ()
    assert diagnostic.fdi_assignments == ()
    assert diagnostic.source_mesh_sha256 == before
    assert diagnostic.preprocessing["source_bytes_modified"] is False
    assert diagnostic.preprocessing["arch"] == "lower"
    assert diagnostic.preprocessing["units"] == "unverified"
    assert diagnostic.runtime_blocker
    assert "pointops" in diagnostic.runtime_blocker
    assert "No fixture substitution" in diagnostic.runtime_blocker
    assert diagnostic.recoverable is True


def test_default_onnx_backend_is_blocked_without_weights(tmp_path) -> None:
    uploaded = tmp_path / "upper.stl"
    uploaded.write_bytes(b"solid patient\nendsolid patient\n")
    before = _sha256(uploaded)
    diagnostic = process_uploaded_case(str(uploaded), ArchType.UPPER)
    assert _sha256(uploaded) == before
    assert diagnostic.state is PipelineState.MODEL_UNAVAILABLE
    assert diagnostic.segmentation_truth_state == "blocked_by_environment"
    assert diagnostic.backend == "onnx"
    assert diagnostic.fixture is False
    assert "No fixture fallback" in diagnostic.failures[0]
    assert "not a ToothInstanceNet substitute" in diagnostic.failures[0]
    assert diagnostic.runtime["detail"]["can_segment_without_external_weights"] is False
    assert diagnostic.runtime["detail"]["cpu_inference_supported"] is True


@pytest.mark.skipif(not (ARTIFACT / "upper.stl").is_file(), reason="official real case missing")
def test_official_real_case_preserves_source_and_does_not_infer() -> None:
    upper = ARTIFACT / "upper.stl"
    lower = ARTIFACT / "lower.stl"
    assert _sha256(upper) == UPPER_SHA
    assert _sha256(lower) == LOWER_SHA
    upper_diag = process_uploaded_case(
        str(upper), ArchType.UPPER, case_id="official", job_id="wave1"
    )
    lower_diag = process_uploaded_case(
        str(lower), ArchType.LOWER, case_id="official", job_id="wave1"
    )
    assert _sha256(upper) == UPPER_SHA
    assert _sha256(lower) == LOWER_SHA
    for diagnostic, arch, sha, vertices, faces in (
        (upper_diag, "upper", UPPER_SHA, 513417, 171139),
        (lower_diag, "lower", LOWER_SHA, 417249, 139083),
    ):
        assert diagnostic.fixture is False
        assert diagnostic.processing_mode == "real_case"
        assert diagnostic.state is PipelineState.MODEL_UNAVAILABLE
        assert diagnostic.segmentation_truth_state == "blocked_by_environment"
        assert diagnostic.tooth_instance_count == 0
        assert diagnostic.source_mesh_sha256 == sha
        assert diagnostic.preprocessing["vertex_count"] == vertices
        assert diagnostic.preprocessing["face_count"] == faces
        assert diagnostic.preprocessing["source_bytes_modified"] is False
        assert diagnostic.preprocessing["coordinate_system"] == "source_file_coordinates"
        assert diagnostic.arch == arch
        assert diagnostic.tooth_instances == ()


def test_failed_segmentation_is_durable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet")
    case_id = client.post("/cases", json={"patient_reference": "wave1-fail"}).json()["id"]
    upper = tmp_path / "upper.stl"
    lower = tmp_path / "lower.stl"
    upper.write_bytes(b"solid u\nendsolid u\n")
    lower.write_bytes(b"solid l\nendsolid l\n")
    case = case_store.get(case_id)
    assert case is not None
    case.meshes = [
        MeshAsset("upper", str(upper), "upper.stl"),
        MeshAsset("lower", str(lower), "lower.stl"),
    ]
    case_store.update(case)
    upper_diag = process_uploaded_case(str(upper), ArchType.UPPER, case_id=case_id, job_id="j")
    lower_diag = process_uploaded_case(str(lower), ArchType.LOWER, case_id=case_id, job_id="j")
    assert upper_diag.state.value in SEGMENTATION_FAILURE_STATES
    assert lower_diag.state.value in SEGMENTATION_FAILURE_STATES
    begin_segmentation_record(
        case_id,
        job_id="j",
        input_hash=compute_case_input_hash(case_id),
        processing_mode="real_case",
    )
    store_arch_result(case_id, "upper", upper_diag.payload(), model_name=upper_diag.model_name)
    store_arch_result(case_id, "lower", lower_diag.payload(), model_name=lower_diag.model_name)
    error = "; ".join([*upper_diag.failures, *lower_diag.failures])
    complete_segmentation_record(case_id, status="failed", error=error)
    record = get_segmentation_record(case_id)
    assert record is not None
    assert record["status"] == "failed"
    assert record["processing_mode"] == "real_case"
    assert record["error"]
    assert "no fixture substitution" in record["error"].lower()
    assert record["arches"]["upper"]["source_mesh_sha256"] == _sha256(upper)
    assert record["arches"]["lower"]["source_mesh_sha256"] == _sha256(lower)
    assert record["arches"]["upper"]["fixture"] is False
    assert record["arches"]["upper"]["segmentation_truth_state"] == "blocked_by_environment"
    assert record["arches"]["upper"]["backend"] == "toothinstancenet"


def test_cancellation_stays_cancelled() -> None:
    case_id = client.post("/cases", json={"patient_reference": "wave1-cancel"}).json()["id"]
    case_store.set_processing(
        case_id,
        {
            "job_id": "wave1-cancel-job",
            "case_id": case_id,
            "stage_status": "PROCESSING",
            "current_stage": "SEGMENTING_BOTH",
            "overall_progress": 20,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_stages": ["PREPARING"],
            "pending_stages": ["SEGMENTING_UPPER"],
            "input_hash": "abc",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    )
    case = case_store.get(case_id)
    assert case is not None
    case.segmentation_results = {
        "status": "processing",
        "job_id": "wave1-cancel-job",
        "arches": {},
    }
    case_store.update(case)
    result = cancel_processing(case_id)
    assert result["stage_status"] == "CANCELLED"
    seg = getattr(case_store.get(case_id), "segmentation_results", None)
    assert seg["status"] == "cancelled"


def test_restart_preserves_interrupted_semantics(tmp_path) -> None:
    store_path = tmp_path / "cases.json"
    store = InMemoryCaseStore(store_path)
    case = Case(patient_reference="wave1-restart")
    store.add(case)
    store.set_processing(
        case.id,
        {
            "job_id": "dead-job",
            "case_id": case.id,
            "stage_status": "PROCESSING",
            "current_stage": "SEGMENTING_UPPER",
            "overall_progress": 30,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_stages": [],
            "pending_stages": ["SEGMENTING_UPPER"],
        },
    )
    stored = store.get(case.id)
    assert stored is not None
    stored.segmentation_results = {
        "status": "processing",
        "job_id": "dead-job",
        "arches": {},
    }
    store.update(store.get(case.id))
    recovered = InMemoryCaseStore(store_path)
    status = recovered.get_processing(case.id)
    assert status is not None
    assert status["stage_status"] == "INTERRUPTED"
    assert status["error_code"] == "PROCESS_RESTARTED"
    seg = recovered.get(case.id).segmentation_results
    assert seg["status"] == "interrupted"
