"""P7 — Performance, reliability, and scale gates."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.session_persistence import load_session, session_path
from app.store import InMemoryCaseStore, case_store
from app.treatment_sessions import TreatmentSession, TreatmentSessionStore, treatment_sessions
from domain.case.models import Case
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
    _validation_worker_count,
)


@pytest.fixture(autouse=True)
def _clear_stores(tmp_path, monkeypatch):
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("ALIGNERSTUDIO_VALIDATION_WORKERS", "2")
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    case_store.clear()
    treatment_sessions.clear()
    yield
    case_store.clear()
    treatment_sessions.clear()

client = TestClient(app)


def test_duplicate_processing_returns_same_job_id() -> None:
    case_id = client.post("/cases", json={"patient_reference": "dup"}).json()["id"]
    case_store.set_processing(
        case_id,
        {
            "job_id": "active-job",
            "case_id": case_id,
            "stage_status": "PROCESSING",
            "current_stage": "SEGMENTING_UPPER",
            "overall_progress": 20,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_stages": [],
            "pending_stages": ["SEGMENTING_UPPER"],
            "error_state": False,
            "error_code": None,
            "user_message": "Analyzing case",
        },
    )
    from app.processing import start_processing

    first = start_processing(case_id)
    second = start_processing(case_id)
    assert first["job_id"] == "active-job"
    assert second["job_id"] == "active-job"
    assert first["stage_status"] == "PROCESSING"
    assert second["stage_status"] == "PROCESSING"


def test_stale_processing_recovered_on_store_reload(tmp_path) -> None:
    store_path = tmp_path / "cases.json"
    store = InMemoryCaseStore(store_path)
    case = Case(patient_reference="stale")
    store.add(case)
    store.set_processing(
        case.id,
        {
            "job_id": "stale-job",
            "case_id": case.id,
            "stage_status": "PROCESSING",
            "current_stage": "BUILDING_PLAN",
            "overall_progress": 70,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_stages": [],
            "pending_stages": ["BUILDING_PLAN"],
        },
    )
    recovered = InMemoryCaseStore(store_path)
    status = recovered.get_processing(case.id)
    assert status is not None
    assert status["stage_status"] == "FAILED"
    assert status["error_code"] == "PROCESS_RESTARTED"
    assert "interrupted" in status["user_message"].lower()


def test_treatment_session_survives_process_local_restart(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)

    first = TreatmentSessionStore()
    session = first.create_engineering_fixture("persist-case")
    path = session_path("persist-case")
    assert path.is_file()
    assert load_session("persist-case") is not None

    second = TreatmentSessionStore()
    restored = second.get("persist-case")
    assert restored.proposal.plan_id == session.proposal.plan_id
    assert restored.staging.staging_id == session.staging.staging_id
    assert restored.validation.report_id == session.validation.report_id
    assert restored.source_kind == session.source_kind


def test_validated_real_case_compose_keeps_intelligence_lazy() -> None:
    """P6 regression guard: validated_real_case compose must not expand alternatives."""
    store = TreatmentSessionStore()
    calls: list[bool] = []
    original = store._intelligence.generate

    def tracking_generate(*args, **kwargs):
        calls.append(bool(kwargs.get("generate_alternatives", True)))
        return original(*args, **kwargs)

    store._intelligence.generate = tracking_generate  # type: ignore[method-assign]
    session = store.create_engineering_fixture("demo-expand")
    assert session.source_kind == "development_treatment_fixture"
    assert calls and calls[-1] is True

    # Force the real-case source_kind path through _attach_intelligence.
    calls.clear()
    shell = TreatmentSession(
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        adjuncts=session.adjuncts,
        source_kind="validated_real_case",
        experimental=True,
        planning_mode="semantic_only_experimental",
    )
    attached = store._attach_intelligence(shell)
    assert calls == [False]
    assert attached.intelligence is not None
    assert len(attached.intelligence.candidates) == 1


def test_unmoved_vertex_reuse_enables_cross_stage_cache_hits() -> None:
    """Staging must reuse vertex tuple identity for unmoved teeth."""
    store = TreatmentSessionStore()
    session = store.create_engineering_fixture("cache-case")
    stages = session.staging.stages
    assert len(stages) >= 2
    # Demo fixture moves some teeth; unmoved teeth share source vertex objects across stages.
    shared = 0
    for first, second in zip(stages[0].tooth_states, stages[1].tooth_states, strict=False):
        if first.tooth_ref == second.tooth_ref and first.vertices is second.vertices:
            shared += 1
    assert shared >= 1


def test_validation_worker_count_respects_env(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_VALIDATION_WORKERS", "3")
    assert _validation_worker_count() == 3
    monkeypatch.delenv("ALIGNERSTUDIO_VALIDATION_WORKERS", raising=False)
    assert _validation_worker_count() == 1
    monkeypatch.setenv("ALIGNERSTUDIO_VALIDATION_WORKERS", "0")
    assert _validation_worker_count() == 1


def test_parallel_validation_matches_serial_on_fixture(monkeypatch) -> None:
    store = TreatmentSessionStore()
    session = store.create_engineering_fixture("parity-case")
    staging = session.staging
    cfg = GeometricValidationConfiguration(1.0, 0.001, 0.0)
    monkeypatch.setenv("ALIGNERSTUDIO_VALIDATION_WORKERS", "1")
    serial = GeometricValidationEngine().validate(staging, cfg)
    monkeypatch.setenv("ALIGNERSTUDIO_VALIDATION_WORKERS", "4")
    parallel = GeometricValidationEngine().validate(staging, cfg)
    assert serial.report_id == parallel.report_id
    assert serial.status == parallel.status
    for left, right in zip(serial.stage_results, parallel.stage_results, strict=True):
        assert [
            (item.tooth_a, item.tooth_b, item.measured_distance) for item in left.proximity_results
        ] == [
            (item.tooth_a, item.tooth_b, item.measured_distance) for item in right.proximity_results
        ]
        assert [
            (item.tooth_a, item.tooth_b, item.intersects) for item in left.collision_results
        ] == [
            (item.tooth_a, item.tooth_b, item.intersects) for item in right.collision_results
        ]


def test_repeated_exports_are_stable() -> None:
    case_id = client.post("/cases/demo").json()["case"]["id"]
    first = client.post(f"/cases/{case_id}/export/verify").json()
    second = client.post(f"/cases/{case_id}/export/verify").json()
    assert first["verified"] is True
    assert second["verified"] is True
    assert first["treatment_plan_id"] == second["treatment_plan_id"]
    assert first["hash_mismatches"] == []
    assert second["hash_mismatches"] == []
    assert first["missing_files"] == []
    assert second["missing_files"] == []


def test_session_persistence_rejects_corrupt_payload(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path))
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path)
    path = session_path("bad")
    path.write_bytes(b"not-a-session")
    assert load_session("bad") is None
