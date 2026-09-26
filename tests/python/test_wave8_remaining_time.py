"""Wave 8 remaining-time, history, and poll-adjacent processing rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.operation_history import (
    clear_operation_history,
    record_completed_operation,
    remaining_time_for_case,
    samples_snapshot,
)
from app.processing import cancel_processing, live_processing_status
from app.store import case_store
from domain.case.models import Case
from engines.performance.remaining_time import (
    NO_RELIABLE_REMAINING_TIME,
    duration_class,
    estimate_remaining,
)


def _sample(duration: float, *, environment: str = "test-host", input_class: str = "both-arches") -> dict:
    return {
        "operation_id": "case-processing",
        "environment_id": environment,
        "input_class": input_class,
        "duration_seconds": duration,
    }


def test_no_samples_and_elapsed_alone_do_not_estimate() -> None:
    result = estimate_remaining(
        [],
        elapsed_seconds=900,
        operation_id="case-processing",
        environment_id="test-host",
        input_class="both-arches",
    )
    assert result["kind"] == "none"
    assert result["seconds"] is None
    assert result["label"] == NO_RELIABLE_REMAINING_TIME
    assert "overall_progress" not in result
    assert duration_class(1) == "fast"
    assert duration_class(10) == "medium"
    assert duration_class(60) == "long"
    assert duration_class(400) == "very_long"


def test_one_sample_is_coarse_and_other_hardware_is_ignored() -> None:
    result = estimate_remaining(
        [_sample(600), _sample(600, environment="other-computer")],
        elapsed_seconds=60,
        operation_id="case-processing",
        environment_id="test-host",
        input_class="both-arches",
    )
    assert result["kind"] == "coarse"
    assert result["sample_count"] == 1
    assert result["seconds"] == 540
    assert result["qualifier"] == "estimated"
    assert "Uncertainty is high" in result["label"]
    assert "guarantee" not in result["label"].split(".")[0]


def test_tight_history_is_measured_and_out_of_range_is_none() -> None:
    samples = [_sample(duration) for duration in (100, 110, 120, 130)]
    measured = estimate_remaining(
        samples,
        elapsed_seconds=40,
        operation_id="case-processing",
        environment_id="test-host",
        input_class="both-arches",
    )
    assert measured["kind"] == "measured"
    assert measured["seconds"] == 75
    assert measured["confidence"] == 0.7
    assert "estimated" in measured["label"]
    assert "Not a guarantee" in measured["label"]
    outside = estimate_remaining(
        samples,
        elapsed_seconds=800,
        operation_id="case-processing",
        environment_id="test-host",
        input_class="both-arches",
    )
    assert outside["kind"] == "none"
    assert outside["seconds"] is None


def test_live_processing_status_has_no_estimate_until_this_computer_has_history() -> None:
    clear_operation_history()
    case_id = "wave8-no-history"
    case_store.add(Case(id=case_id, patient_reference="wave8"))
    started = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
    case_store.set_processing(
        case_id,
        {
            "job_id": "job-wave8",
            "case_id": case_id,
            "overall_progress": 20,
            "current_stage": "BUILDING_PLAN",
            "stage_status": "PROCESSING",
            "stage_progress": None,
            "completed_stages": [],
            "pending_stages": [],
            "error_state": False,
            "error_code": None,
            "user_message": "Preparing treatment setup",
            "started_at": started,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "heartbeat_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "elapsed_seconds": 0,
        },
    )
    status = live_processing_status(case_id)
    assert status is not None
    assert status["overall_progress"] == 20
    assert status["remaining_time"]["kind"] == "none"
    assert status["remaining_time"]["label"] == NO_RELIABLE_REMAINING_TIME
    case_store.clear()
    clear_operation_history()


def test_recorded_completions_feed_the_same_case_class_only() -> None:
    clear_operation_history()
    case_id = "wave8-history"
    case_store.add(Case(id=case_id, patient_reference="wave8-history"))
    for duration in (100, 110, 120, 130):
        record_completed_operation(
            operation_id="case-processing",
            input_class="unknown",
            duration_seconds=duration,
        )
    record_completed_operation(
        operation_id="case-processing",
        input_class="both-arches",
        duration_seconds=20,
    )
    started = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
    case_store.set_processing(
        case_id,
        {
            "job_id": "job-wave8-history",
            "case_id": case_id,
            "overall_progress": 40,
            "current_stage": "BUILDING_PLAN",
            "stage_status": "PROCESSING",
            "stage_progress": None,
            "completed_stages": [],
            "pending_stages": [],
            "error_state": False,
            "error_code": None,
            "user_message": "Preparing treatment setup",
            "started_at": started,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "heartbeat_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "elapsed_seconds": 0,
        },
    )
    estimate = remaining_time_for_case(case_id, 40)
    assert estimate["kind"] == "measured"
    assert estimate["input_class"] == "unknown"
    assert estimate["sample_count"] == 4
    case_store.clear()
    clear_operation_history()


def test_cancel_does_not_record_a_duration() -> None:
    clear_operation_history()
    case_id = "wave8-cancel"
    case_store.add(Case(id=case_id, patient_reference="wave8-cancel"))
    started = datetime.now(timezone.utc).isoformat()
    case_store.set_processing(
        case_id,
        {
            "job_id": "job-wave8-cancel",
            "case_id": case_id,
            "overall_progress": 10,
            "current_stage": "PREPARING",
            "stage_status": "PROCESSING",
            "stage_progress": 0,
            "completed_stages": [],
            "pending_stages": [],
            "error_state": False,
            "error_code": None,
            "user_message": "Analyzing case",
            "started_at": started,
            "updated_at": started,
            "heartbeat_at": started,
            "completed_at": None,
            "elapsed_seconds": 3,
        },
    )
    before = len(samples_snapshot())
    cancelled = cancel_processing(case_id)
    assert cancelled["stage_status"] == "CANCELLED"
    live = live_processing_status(case_id)
    assert live is not None
    assert live["stage_status"] == "CANCELLED"
    assert live["remaining_time"]["kind"] == "none"
    assert len(samples_snapshot()) == before
    case_store.clear()
    clear_operation_history()
