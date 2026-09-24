"""Durable, process-local background processing orchestration."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Lock
from time import perf_counter
from uuid import uuid4

from fastapi import HTTPException

from app.pipeline_diagnostics import process_uploaded_case
from app.store import case_store
from domain.tooth.identification import ArchType

STAGES = (
    "PREPARING",
    "VALIDATING_SCANS",
    "SEGMENTING_UPPER",
    "SEGMENTING_LOWER",
    "BUILDING_PLAN",
    "VALIDATING_PLAN",
    "FINALIZING",
)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="alignerstudio-processing")
_lock = Lock()
logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _elapsed_seconds(started_at: str) -> int:
    elapsed = datetime.now(UTC) - datetime.fromisoformat(started_at)
    return max(0, int(elapsed.total_seconds()))


def live_processing_status(case_id: str) -> dict | None:
    """Return the persisted job status with elapsed_seconds recomputed live while PROCESSING.

    Terminal jobs (COMPLETED/FAILED/CANCELLED) keep their final persisted elapsed value.
    """
    status = case_store.get_processing(case_id)
    if status is None:
        return None
    if status.get("stage_status") == "PROCESSING" and status.get("started_at"):
        status = {**status, "elapsed_seconds": _elapsed_seconds(status["started_at"])}
    return status


def _status(case_id: str, job_id: str, *, current_stage: str, stage_status: str,
            overall_progress: int, stage_progress: int | None, completed: list[str],
            pending: list[str], error_state: bool = False, error_code: str | None = None,
            message: str = "") -> dict:
    current = case_store.get_processing(case_id) or {}
    started_at = current.get("started_at", _now())
    elapsed_seconds = _elapsed_seconds(started_at)
    payload = {
        "job_id": job_id,
        "case_id": case_id,
        "overall_progress": max(0, min(100, overall_progress)),
        "current_stage": current_stage,
        "stage_status": stage_status,
        "stage_progress": stage_progress,
        "completed_stages": completed,
        "pending_stages": pending,
        "error_state": error_state,
        "error_code": error_code,
        "user_message": message,
        "technical_diagnostic": current.get("technical_diagnostic"),
        "started_at": current.get("started_at", _now()),
        "updated_at": _now(),
        "elapsed_seconds": elapsed_seconds,
        "upper_status": "COMPLETED" if "SEGMENTING_UPPER" in completed else "PROCESSING" if current_stage == "SEGMENTING_UPPER" else "PENDING",
        "lower_status": "COMPLETED" if "SEGMENTING_LOWER" in completed else "PROCESSING" if current_stage == "SEGMENTING_LOWER" else "PENDING",
        "planning_status": "COMPLETED" if "BUILDING_PLAN" in completed else "PROCESSING" if current_stage in {"BUILDING_PLAN", "VALIDATING_PLAN"} else "PENDING",
        "completed_at": _now() if stage_status in {"COMPLETED", "FAILED", "CANCELLED"} else None,
    }
    case_store.set_processing(case_id, payload)
    logger.info(
        "PROCESSING_TRANSITION case_id=%s job_id=%s stage=%s status=%s progress=%s message=%s",
        case_id, job_id, current_stage, stage_status, payload["overall_progress"], message,
    )
    return payload


def start_processing(case_id: str) -> dict:
    case = case_store.get(case_id)
    if case is None:
        raise KeyError("Case not found")
    with _lock:
        current = case_store.get_processing(case_id)
        if current and current["stage_status"] == "PROCESSING":
            return current
        job_id = str(uuid4())
        other_active = any(
            item.get("stage_status") == "PROCESSING"
            for existing_case in case_store.list()
            if existing_case.id != case_id
            for item in [case_store.get_processing(existing_case.id) or {}]
        )
        initial = _status(
            case_id, job_id, current_stage="PREPARING", stage_status="PROCESSING",
            overall_progress=0, stage_progress=None, completed=[], pending=list(STAGES),
            message="Queued behind another case analysis" if other_active else "Analyzing case",
        )
        logger.info("PROCESSING_CREATED case_id=%s job_id=%s", case_id, job_id)
        future = _executor.submit(_run, case_id, job_id)
        future.add_done_callback(lambda completed: _handle_worker_exit(case_id, job_id, completed))
        return initial


def _handle_worker_exit(case_id: str, job_id: str, future: Future[None]) -> None:
    try:
        error = future.exception()
    except BaseException as worker_exit:
        error = worker_exit
    if error is None:
        return
    logger.error(
        "PROCESSING_WORKER_EXITED case_id=%s job_id=%s error=%s",
        case_id,
        job_id,
        error,
    )
    current = case_store.get_processing(case_id) or {}
    if current.get("job_id") != job_id or current.get("stage_status") != "PROCESSING":
        return
    _fail(
        case_id,
        job_id,
        current.get("completed_stages", []),
        "Processing could not be completed for this case",
        f"{type(error).__name__}: {error}",
    )


def _run(case_id: str, job_id: str) -> None:
    completed: list[str] = []
    try:
        _status(case_id, job_id, current_stage="VALIDATING_SCANS", stage_status="PROCESSING",
                overall_progress=5, stage_progress=100, completed=[], pending=list(STAGES[2:]),
                message="Validating scans")
        case = case_store.get(case_id)
        if case is None:
            raise KeyError("Case not found")
        if {mesh.arch for mesh in case.meshes} != {"upper", "lower"}:
            raise ValueError("Both upper and lower scans are required before processing")
        completed.append("VALIDATING_SCANS")
        _status(case_id, job_id, current_stage="SEGMENTING_UPPER", stage_status="PROCESSING",
                overall_progress=10, stage_progress=None, completed=completed, pending=list(STAGES[3:]),
                message="Segmenting upper arch")
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                "SEGMENTING_UPPER": pool.submit(process_uploaded_case, next(m.file_path for m in case.meshes if m.arch == "upper"), ArchType.UPPER),
                "SEGMENTING_LOWER": pool.submit(process_uploaded_case, next(m.file_path for m in case.meshes if m.arch == "lower"), ArchType.LOWER),
            }
            upper = futures["SEGMENTING_UPPER"].result()
            completed.append("SEGMENTING_UPPER")
            _status(case_id, job_id, current_stage="SEGMENTING_LOWER", stage_status="PROCESSING",
                    overall_progress=55, stage_progress=None, completed=completed, pending=list(STAGES[4:]),
                    message="Segmenting lower arch")
            lower = futures["SEGMENTING_LOWER"].result()
        completed.append("SEGMENTING_LOWER")
        if upper.state.value != "identification_incomplete" or lower.state.value != "identification_incomplete":
            raise ValueError("Segmentation completed without a reviewable identification result")
        _status(case_id, job_id, current_stage="BUILDING_PLAN", stage_status="PROCESSING",
                overall_progress=70, stage_progress=None, completed=completed, pending=list(STAGES[4:]),
                message="Preparing treatment setup")
        from app.routers.cases import generate_plan_with_progress

        def _report_planning_progress(progress: int, message: str) -> None:
            _status(case_id, job_id, current_stage="BUILDING_PLAN", stage_status="PROCESSING",
                    overall_progress=progress, stage_progress=None, completed=completed,
                    pending=list(STAGES[4:]), message=message)

        planning_started = perf_counter()
        logger.info("PLAN_BUILDING_STARTED case_id=%s job_id=%s", case_id, job_id)
        generate_plan_with_progress(case_id, progress_callback=_report_planning_progress)
        logger.info(
            "PLAN_BUILDING_COMPLETED case_id=%s job_id=%s duration_ms=%.0f",
            case_id,
            job_id,
            (perf_counter() - planning_started) * 1000,
        )
        completed.append("BUILDING_PLAN")
        _status(case_id, job_id, current_stage="VALIDATING_PLAN", stage_status="PROCESSING",
                overall_progress=88, stage_progress=None, completed=completed, pending=["FINALIZING"],
                message="Validating setup")
        completed.append("VALIDATING_PLAN")
        _status(case_id, job_id, current_stage="FINALIZING", stage_status="PROCESSING",
                overall_progress=96, stage_progress=100, completed=completed, pending=[],
                message="Finalizing workspace")
        completed.append("FINALIZING")
        _status(case_id, job_id, current_stage="FINALIZING", stage_status="COMPLETED",
                overall_progress=100, stage_progress=100, completed=completed, pending=[],
                message="Case ready")
    except HTTPException as error:
        _fail(case_id, job_id, completed, str(error.detail), f"HTTP_{error.status_code}")
    except Exception as error:
        _fail(case_id, job_id, completed, "Processing could not be completed for this case", str(error))


def _fail(case_id: str, job_id: str, completed: list[str], message: str, diagnostic: str) -> None:
    current = case_store.get_processing(case_id) or {}
    current["technical_diagnostic"] = diagnostic
    case_store.set_processing(case_id, current)
    _status(case_id, job_id, current_stage=current.get("current_stage", "PREPARING"),
            stage_status="FAILED", overall_progress=current.get("overall_progress", 0),
            stage_progress=current.get("stage_progress"), completed=completed,
            pending=[stage for stage in STAGES if stage not in completed], error_state=True,
            error_code="PROCESSING_FAILED", message=message)
