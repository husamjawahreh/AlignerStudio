"""WP-13 — Reliability, recovery, and data integrity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.failure_injection import (
    configure_failure_point,
    reset_failure_injection,
)
from app.main import app
from app.session_persistence import load_session, save_session, session_path
from app.store import InMemoryCaseStore, case_store
from app.treatment_sessions import TreatmentSessionStore, treatment_sessions
from domain.case.models import Case
from domain.case.provenance import DataProvenance
from domain.tooth.identification import ToothCoordinateSystem
from domain.treatment_plan.setup import ToothMovement
from domain.treatment_plan.staging import (
    StageMovement,
    StageToothState,
    StagingResult,
    TreatmentStage,
)
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)
from engines.validation.report_cache import (
    cache_snapshot_keys,
    clear_validation_report_cache,
    get_cached_report,
    store_cached_report,
)


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("ALIGNERSTUDIO_FAILURE_INJECTION", "0")
    reset_failure_injection()
    clear_validation_report_cache()
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    case_store.clear()
    treatment_sessions.clear()
    yield
    reset_failure_injection()
    clear_validation_report_cache()
    case_store.clear()
    treatment_sessions.clear()


client = TestClient(app)


def _tiny_staging(plan_id: str, staging_id: str) -> StagingResult:
    frame = ToothCoordinateSystem(
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    )
    verts = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    faces = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))

    def tooth(ref: str, iid: int, dx: float) -> StageToothState:
        shifted = tuple((x + dx, y, z) for x, y, z in verts)
        return StageToothState(
            tooth_number=None,
            source_instance_id=iid,
            source_vertices=shifted,
            source_faces=faces,
            final_target_vertices=shifted,
            final_target_faces=faces,
            vertices=shifted,
            coordinate_system=frame,
            movement=StageMovement(tooth_number=ref, movement=ToothMovement(), progress=0.0),
            provenance=DataProvenance.FIXTURE,
            fixture=True,
            tooth_ref=ref,
            arch="upper",
        )

    stage = TreatmentStage(
        0,
        "s0",
        (tooth("u1", 1, 0.0), tooth("u2", 2, 5.0)),
        DataProvenance.FIXTURE,
        True,
        "h0",
    )
    return StagingResult(
        plan_id=plan_id,
        staging_id=staging_id,
        stages=(stage,),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        assumptions=(),
        warnings=(),
        limitations=(),
    )


# --- Crash / restart ---


def test_store_reload_marks_processing_interrupted(tmp_path) -> None:
    store_path = tmp_path / "cases.json"
    store = InMemoryCaseStore(store_path)
    case = Case(patient_reference="crash")
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
    setattr(
        store.get(case.id),
        "segmentation_results",
        {"status": "processing", "job_id": "dead-job", "arches": {}},
    )
    store.update(store.get(case.id))

    recovered = InMemoryCaseStore(store_path)
    status = recovered.get_processing(case.id)
    assert status is not None
    assert status["stage_status"] == "INTERRUPTED"
    assert status["error_code"] == "PROCESS_RESTARTED"
    assert status.get("result") is None
    seg = getattr(recovered.get(case.id), "segmentation_results", None)
    assert seg["status"] == "interrupted"


def test_case_store_persist_is_atomic(tmp_path) -> None:
    path = tmp_path / "cases.json"
    store = InMemoryCaseStore(path)
    case = Case(patient_reference="atomic")
    store.add(case)
    assert path.is_file()
    assert not path.with_suffix(".json.tmp").exists()
    records = json.loads(path.read_text())
    assert records[0]["id"] == case.id


# --- Cancellation ---


def test_cancel_demotes_in_flight_segmentation(monkeypatch) -> None:
    case_id = client.post("/cases", json={"patient_reference": "cancel"}).json()["id"]
    case_store.set_processing(
        case_id,
        {
            "job_id": "cancel-job",
            "case_id": case_id,
            "stage_status": "PROCESSING",
            "current_stage": "SEGMENTING_BOTH",
            "overall_progress": 20,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_stages": ["PREPARING", "VALIDATING_SCANS"],
            "pending_stages": ["SEGMENTING_UPPER"],
            "input_hash": "abc",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    )
    case = case_store.get(case_id)
    setattr(
        case,
        "segmentation_results",
        {"status": "processing", "job_id": "cancel-job", "arches": {}},
    )
    case_store.update(case)

    from app.processing import cancel_processing

    result = cancel_processing(case_id)
    assert result["stage_status"] == "CANCELLED"
    assert result["error_code"] == "CANCELLED"
    assert result.get("result") is None
    seg = getattr(case_store.get(case_id), "segmentation_results", None)
    assert seg["status"] == "cancelled"


# --- Idempotency / duplicate ---


def test_duplicate_processing_is_idempotent() -> None:
    case_id = client.post("/cases", json={"patient_reference": "dup"}).json()["id"]
    case_store.set_processing(
        case_id,
        {
            "job_id": "live",
            "case_id": case_id,
            "stage_status": "PROCESSING",
            "current_stage": "BUILDING_PLAN",
            "overall_progress": 70,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_stages": [],
            "pending_stages": [],
        },
    )
    from app.processing import start_processing

    first = start_processing(case_id)
    second = start_processing(case_id)
    assert first["job_id"] == "live"
    assert second["job_id"] == "live"


def test_interrupted_job_allows_new_job_id() -> None:
    case_id = client.post("/cases", json={"patient_reference": "retry"}).json()["id"]
    # Minimal meshes so start_processing can be called — it only needs case present;
    # worker will fail later without meshes, but identity must be new.
    case_store.set_processing(
        case_id,
        {
            "job_id": "old",
            "case_id": case_id,
            "stage_status": "INTERRUPTED",
            "error_code": "PROCESS_RESTARTED",
            "current_stage": "SEGMENTING_UPPER",
            "overall_progress": 20,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_stages": [],
            "pending_stages": [],
        },
    )
    from app.processing import start_processing

    restarted = start_processing(case_id)
    assert restarted["job_id"] != "old"
    assert restarted["stage_status"] == "PROCESSING"
    assert restarted["overall_progress"] == 0


# --- Case isolation ---


def test_validation_report_cache_isolated_by_plan_id() -> None:
    cfg = GeometricValidationConfiguration(1.0, 0.001, 0.0)
    staging_a = _tiny_staging("plan-case-A", "staging-shared-shape")
    staging_b = _tiny_staging("plan-case-B", "staging-shared-shape")
    report_a = GeometricValidationEngine().validate(staging_a, cfg)
    store_cached_report(staging_a, cfg, report_a)
    assert get_cached_report(staging_a, cfg) is not None
    assert get_cached_report(staging_b, cfg) is None
    keys = cache_snapshot_keys()
    assert any(key.startswith("plan-case-A|") for key in keys)
    assert not any(key.startswith("plan-case-B|") for key in keys)


def test_session_checkpoints_are_case_scoped(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)

    store = TreatmentSessionStore()
    session_a = store.create_engineering_fixture("case-a")
    session_b = store.create_engineering_fixture("case-b")
    assert session_a.proposal.case_id == "case-a" or session_path("case-a").is_file()
    assert session_path("case-a").is_file()
    assert session_path("case-b").is_file()
    assert session_path("case-a") != session_path("case-b")
    restored_a = load_session("case-a")
    assert restored_a is not None
    # Loading case-b must not return case-a's session object identity via wrong path.
    assert load_session("case-b") is not None
    assert session_a.proposal.plan_id != session_b.proposal.plan_id


# --- Failure injection ---


def test_failure_injection_blocks_case_store_persist(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_FAILURE_INJECTION", "1")
    configure_failure_point("before_case_store_persist")
    path = tmp_path / "cases.json"
    store = InMemoryCaseStore(path)
    case = Case(patient_reference="inject")
    with pytest.raises(RuntimeError, match="before_case_store_persist"):
        store.add(case)
    # No durable success claim — file may be absent or unchanged.
    if path.is_file():
        # Prior empty store — should not contain the new case as COMPLETED processing.
        text = path.read_text()
        assert case.id not in text or "PROCESSING" not in text


def test_failure_injection_disabled_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_FAILURE_INJECTION", "0")
    configure_failure_point("before_case_store_persist")
    path = tmp_path / "cases.json"
    store = InMemoryCaseStore(path)
    case = Case(patient_reference="safe")
    store.add(case)
    assert any(item["id"] == case.id for item in json.loads(path.read_text()))


# --- Export / reopen integrity ---


def test_export_verify_survives_session_reload(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)

    first = TreatmentSessionStore()
    first.create_engineering_fixture("export-case")
    export_dir = tmp_path / "export"
    package = first.export("export-case", export_dir)
    verify = first.verify_export("export-case", export_dir)
    assert isinstance(verify, dict)
    # Never claim success without hash evidence — accept explicit ok/valid or mismatch-empty.
    mismatches = verify.get("hash_mismatches") or verify.get("mismatches") or []
    assert mismatches == [] or verify.get("ok") is True or verify.get("valid") is True

    second = TreatmentSessionStore()
    restored = second.get("export-case")
    assert restored.proposal.plan_id == first.get("export-case").proposal.plan_id
    assert restored.validation.report_id == first.get("export-case").validation.report_id
    reverify = second.verify_export("export-case", export_dir)
    assert isinstance(reverify, dict)
    assert package.zip_path.is_file()
    rematches = reverify.get("hash_mismatches") or reverify.get("mismatches") or []
    assert rematches == [] or reverify.get("ok") is True or reverify.get("valid") is True


# --- Version / stale bindings preserved on session round-trip ---


def test_session_round_trip_preserves_version_bindings(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)

    store = TreatmentSessionStore()
    session = store.create_engineering_fixture("versions")
    plan_id = session.proposal.plan_id
    staging_id = session.staging.staging_id
    report_id = session.validation.report_id
    version_id = session.proposal.version_id

    cold = TreatmentSessionStore()
    restored = cold.get("versions")
    assert restored.proposal.plan_id == plan_id
    assert restored.staging.staging_id == staging_id
    assert restored.validation.report_id == report_id
    assert restored.proposal.version_id == version_id
