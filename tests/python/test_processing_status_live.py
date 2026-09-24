"""N4.1: elapsed_seconds must be computed live on read, not frozen at write time."""

from datetime import datetime, timedelta, timezone

from app.processing import live_processing_status
from app.store import case_store

from domain.case.models import Case


def _seed_processing_job(case_id: str, *, stage_status: str, started_at: str) -> None:
    case_store.set_processing(
        case_id,
        {
            "job_id": "job-1",
            "case_id": case_id,
            "overall_progress": 70,
            "current_stage": "BUILDING_PLAN",
            "stage_status": stage_status,
            "stage_progress": None,
            "completed_stages": [],
            "pending_stages": [],
            "error_state": False,
            "error_code": None,
            "user_message": "Preparing treatment setup",
            "technical_diagnostic": None,
            "started_at": started_at,
            "updated_at": started_at,
            "completed_at": None,
            "elapsed_seconds": 0,
        },
    )


def test_processing_job_elapsed_seconds_increases_across_live_reads() -> None:
    case_id = "live-status-case"
    case_store.add(Case(id=case_id, patient_reference="live-status"))
    started_at = (datetime.now(timezone.utc) - timedelta(seconds=125)).isoformat()
    _seed_processing_job(case_id, stage_status="PROCESSING", started_at=started_at)

    first = live_processing_status(case_id)
    assert first is not None
    assert first["elapsed_seconds"] >= 125

    later_started_at = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()
    _seed_processing_job(case_id, stage_status="PROCESSING", started_at=later_started_at)
    second = live_processing_status(case_id)
    assert second is not None
    assert second["elapsed_seconds"] >= 200
    assert second["elapsed_seconds"] > first["elapsed_seconds"]
    case_store.clear()


def test_completed_job_keeps_stable_persisted_elapsed_seconds() -> None:
    case_id = "completed-status-case"
    case_store.add(Case(id=case_id, patient_reference="completed-status"))
    started_at = (datetime.now(timezone.utc) - timedelta(seconds=500)).isoformat()
    _seed_processing_job(case_id, stage_status="COMPLETED", started_at=started_at)
    persisted = case_store.get_processing(case_id)
    assert persisted is not None
    persisted["elapsed_seconds"] = 42
    case_store.set_processing(case_id, persisted)

    first = live_processing_status(case_id)
    second = live_processing_status(case_id)
    assert first is not None and second is not None
    assert first["elapsed_seconds"] == 42
    assert second["elapsed_seconds"] == 42
    case_store.clear()


def test_failed_job_keeps_stable_persisted_elapsed_seconds() -> None:
    case_id = "failed-status-case"
    case_store.add(Case(id=case_id, patient_reference="failed-status"))
    started_at = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    _seed_processing_job(case_id, stage_status="FAILED", started_at=started_at)
    persisted = case_store.get_processing(case_id)
    assert persisted is not None
    persisted["elapsed_seconds"] = 17
    case_store.set_processing(case_id, persisted)

    status = live_processing_status(case_id)
    assert status is not None
    assert status["elapsed_seconds"] == 17
    case_store.clear()


def test_missing_job_returns_none() -> None:
    case_id = "no-job-case"
    case_store.add(Case(id=case_id, patient_reference="no-job"))
    assert live_processing_status(case_id) is None
    case_store.clear()
