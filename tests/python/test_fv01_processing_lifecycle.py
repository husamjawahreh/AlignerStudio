"""FV-01 — processing job lifecycle: identity, hash, heartbeat, stale, cancel, no progress inheritance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.processing import (
    STALE_HEARTBEAT_SECONDS,
    cancel_processing,
    compute_case_input_hash,
    live_processing_status,
    start_processing,
)
from app.store import case_store
from domain.case.models import Case, MeshAsset


@pytest.fixture(autouse=True)
def _clear_stores(tmp_path, monkeypatch):
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    case_store.clear()
    yield
    case_store.clear()


client = TestClient(app)


def _case_with_meshes(tmp_path: Path, patient: str = "fv01") -> str:
    case_id = client.post("/cases", json={"patient_reference": patient}).json()["id"]
    case = case_store.get(case_id)
    assert case is not None
    upper = tmp_path / "upper.stl"
    lower = tmp_path / "lower.stl"
    upper.write_bytes(b"solid upper\nendsolid upper\n")
    lower.write_bytes(b"solid lower\nendsolid lower\n")
    case.meshes = [
        MeshAsset(arch="upper", file_path=str(upper), original_filename="upper.stl"),
        MeshAsset(arch="lower", file_path=str(lower), original_filename="lower.stl"),
    ]
    case_store.update(case)
    return case_id


def test_new_job_starts_at_zero_with_identity_fields(tmp_path) -> None:
    case_id = _case_with_meshes(tmp_path)
    # Seed a completed high-progress job that must not be inherited.
    case_store.set_processing(
        case_id,
        {
            "job_id": "old-job",
            "case_id": case_id,
            "stage_status": "COMPLETED",
            "current_stage": "FINALIZING",
            "overall_progress": 100,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_stages": ["FINALIZING"],
            "pending_stages": [],
            "error_state": False,
            "error_code": None,
            "user_message": "Case ready",
        },
    )
    started = start_processing(case_id)
    assert started["job_id"] != "old-job"
    assert started["overall_progress"] == 0
    assert started["current_stage"] == "PREPARING"
    assert started["stage_status"] == "PROCESSING"
    assert started["input_hash"]
    assert started["created_at"]
    assert started["started_at"]
    assert started["heartbeat_at"]
    assert started["completed_at"] is None


def test_duplicate_processing_returns_same_job_id(tmp_path) -> None:
    case_id = _case_with_meshes(tmp_path)
    case_store.set_processing(
        case_id,
        {
            "job_id": "active-job",
            "case_id": case_id,
            "stage_status": "PROCESSING",
            "current_stage": "SEGMENTING_BOTH",
            "overall_progress": 20,
            "started_at": datetime.now(UTC).isoformat(),
            "heartbeat_at": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
            "input_hash": "abc",
            "completed_stages": [],
            "pending_stages": ["SEGMENTING_UPPER"],
            "error_state": False,
            "error_code": None,
            "user_message": "Analyzing case",
        },
    )
    first = start_processing(case_id)
    second = start_processing(case_id)
    assert first["job_id"] == "active-job"
    assert second["job_id"] == "active-job"
    assert second["overall_progress"] == 20


def test_stale_heartbeat_marks_job_stale_and_allows_new_identity(tmp_path) -> None:
    case_id = _case_with_meshes(tmp_path)
    stale_time = (datetime.now(UTC) - timedelta(seconds=STALE_HEARTBEAT_SECONDS + 5)).isoformat()
    case_store.set_processing(
        case_id,
        {
            "job_id": "stale-job",
            "case_id": case_id,
            "stage_status": "PROCESSING",
            "current_stage": "BUILDING_PLAN",
            "overall_progress": 82,
            "started_at": stale_time,
            "updated_at": stale_time,
            "heartbeat_at": stale_time,
            "created_at": stale_time,
            "input_hash": "hash",
            "completed_stages": [],
            "pending_stages": ["BUILDING_PLAN"],
            "error_state": False,
            "error_code": None,
            "user_message": "Preparing treatment setup",
        },
    )
    live = live_processing_status(case_id)
    assert live is not None
    assert live["stage_status"] == "STALE"
    assert live["error_code"] == "JOB_STALE"
    assert live["overall_progress"] == 82

    restarted = start_processing(case_id)
    assert restarted["job_id"] != "stale-job"
    assert restarted["overall_progress"] == 0
    assert restarted["current_stage"] == "PREPARING"
    assert restarted["stage_status"] == "PROCESSING"


def test_cancel_processing_sets_cancelled(tmp_path) -> None:
    case_id = _case_with_meshes(tmp_path)
    case_store.set_processing(
        case_id,
        {
            "job_id": "cancel-me",
            "case_id": case_id,
            "stage_status": "PROCESSING",
            "current_stage": "SEGMENTING_BOTH",
            "overall_progress": 15,
            "started_at": datetime.now(UTC).isoformat(),
            "heartbeat_at": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
            "input_hash": "hash",
            "completed_stages": ["PREPARING"],
            "pending_stages": ["VALIDATING_SCANS"],
            "error_state": False,
            "error_code": None,
            "user_message": "Analyzing case",
        },
    )
    cancelled = cancel_processing(case_id)
    assert cancelled["stage_status"] == "CANCELLED"
    assert cancelled["error_code"] == "CANCELLED"
    assert cancelled["job_id"] == "cancel-me"

    response = client.post(f"/cases/{case_id}/processing/cancel")
    assert response.status_code == 200
    assert response.json()["stage_status"] == "CANCELLED"


def test_input_hash_changes_when_mesh_bytes_change(tmp_path) -> None:
    case_id = _case_with_meshes(tmp_path)
    first = compute_case_input_hash(case_id)
    case = case_store.get(case_id)
    assert case is not None
    Path(case.meshes[0].file_path).write_bytes(b"solid upper changed\nendsolid upper\n")
    second = compute_case_input_hash(case_id)
    assert first != second


def test_never_reports_ready_as_high_progress_running(tmp_path) -> None:
    """Regression: a new job must not open at BUILDING_PLAN mid-progress."""
    case_id = _case_with_meshes(tmp_path)
    started = start_processing(case_id)
    assert started["stage_status"] == "PROCESSING"
    assert started["overall_progress"] == 0
    assert started["current_stage"] == "PREPARING"
    assert started["current_stage"] != "BUILDING_PLAN"
