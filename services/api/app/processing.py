"""Durable, process-local background processing orchestration.

FV-01: every job carries explicit identity, input hash, heartbeat, and
truthful stage/progress. Duplicate in-flight jobs are rejected; stale or
restarted jobs fail closed with a new identity required on retry.
"""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import perf_counter
from uuid import uuid4

from fastapi import HTTPException

from app.pipeline_diagnostics import process_uploaded_case
from app.store import case_store
from domain.tooth.identification import ArchType

# Segmentation outcomes that must become a durable FAILED job. Not COMPLETED.
SEGMENTATION_FAILURE_STATES = frozenset(
    {
        "model_unavailable",
        "blocked_by_environment",
        "segmentation_failed",
        "planning_unavailable",
    }
)

STAGES = (
    "PREPARING",
    "VALIDATING_SCANS",
    "SEGMENTING_UPPER",
    "SEGMENTING_LOWER",
    "BUILDING_PLAN",
    "VALIDATING_PLAN",
    "FINALIZING",
)

# Job-level lifecycle. STALE / INTERRUPTED / CANCELLED are terminal recovered states
# (distinct from FAILED). COMPLETED requires durable completion evidence.
STAGE_STATUSES = frozenset(
    {"PROCESSING", "COMPLETED", "FAILED", "CANCELLED", "STALE", "INTERRUPTED"}
)

# No heartbeat within this window → live status reports STALE and blocks duplicate starts.
STALE_HEARTBEAT_SECONDS = 120

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="alignerstudio-processing")
_lock = Lock()
_active_futures: dict[str, Future[None]] = {}
_cancel_flags: set[str] = set()
logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _elapsed_seconds(started_at: str) -> int:
    elapsed = datetime.now(UTC) - datetime.fromisoformat(started_at)
    return max(0, int(elapsed.total_seconds()))


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def compute_case_input_hash(case_id: str) -> str:
    """Stable hash of case mesh paths + file digests so retries get a new identity when inputs change."""
    case = case_store.get(case_id)
    if case is None:
        return hashlib.sha256(case_id.encode("utf-8")).hexdigest()
    digest = hashlib.sha256()
    digest.update(case_id.encode("utf-8"))
    for mesh in sorted(case.meshes, key=lambda item: (item.arch, item.file_path)):
        digest.update(mesh.arch.encode("utf-8"))
        digest.update(b"\0")
        digest.update(mesh.file_path.encode("utf-8"))
        digest.update(b"\0")
        try:
            path_bytes = open(mesh.file_path, "rb").read()
        except OSError:
            digest.update(b"missing")
        else:
            digest.update(hashlib.sha256(path_bytes).digest())
    return digest.hexdigest()


def _derive_arch_statuses(current_stage: str, completed: list[str]) -> dict[str, str]:
    upper_done = "SEGMENTING_UPPER" in completed
    lower_done = "SEGMENTING_LOWER" in completed
    upper_running = current_stage in {"SEGMENTING_UPPER", "SEGMENTING_BOTH"} or (
        current_stage == "SEGMENTING_LOWER" and not upper_done
    )
    lower_running = current_stage in {"SEGMENTING_LOWER", "SEGMENTING_BOTH"} or (
        current_stage == "SEGMENTING_UPPER" and not lower_done and "SEGMENTING_UPPER" in completed
    )
    # Both arches start together; report both PROCESSING until each completes.
    if current_stage == "SEGMENTING_BOTH":
        upper_running = not upper_done
        lower_running = not lower_done
    return {
        "upper_status": (
            "COMPLETED" if upper_done else "PROCESSING" if upper_running or current_stage.startswith("SEGMENTING") else "PENDING"
        ),
        "lower_status": (
            "COMPLETED" if lower_done else "PROCESSING" if lower_running or current_stage.startswith("SEGMENTING") else "PENDING"
        ),
        "planning_status": (
            "COMPLETED"
            if "BUILDING_PLAN" in completed and "VALIDATING_PLAN" in completed
            else "PROCESSING"
            if current_stage in {"BUILDING_PLAN", "VALIDATING_PLAN"}
            else "PENDING"
        ),
    }


def _mark_stale_if_needed(status: dict) -> dict:
    """If a PROCESSING job has stopped heartbeating and has no live worker, mark STALE.

    Active executor futures keep the job alive: heartbeat is refreshed on read so
    long segmentation stages are not falsely marked stale.
    """
    if status.get("stage_status") != "PROCESSING":
        return status
    job_id = status.get("job_id")
    case_id = status.get("case_id", "")
    future = _active_futures.get(job_id) if job_id else None
    if future is not None and not future.done():
        refreshed = {**status, "heartbeat_at": _now(), "updated_at": _now()}
        if case_id:
            case_store.set_processing(case_id, refreshed)
        return refreshed
    heartbeat = _parse_iso(status.get("heartbeat_at") or status.get("updated_at"))
    if heartbeat is None:
        return status
    age = datetime.now(UTC) - heartbeat
    if age <= timedelta(seconds=STALE_HEARTBEAT_SECONDS):
        return status
    stale = {
        **status,
        "stage_status": "STALE",
        "error_state": True,
        "error_code": "JOB_STALE",
        "user_message": "Case analysis stopped responding. Start analysis again.",
        "technical_diagnostic": (
            f"No heartbeat for {int(age.total_seconds())}s "
            f"(threshold={STALE_HEARTBEAT_SECONDS}s); previous job_id={job_id}"
        ),
        "updated_at": _now(),
        "completed_at": _now(),
        "heartbeat_at": _now(),
    }
    if case_id:
        case_store.set_processing(case_id, stale)
        if job_id:
            _active_futures.pop(job_id, None)
            _cancel_flags.discard(job_id)
        logger.warning(
            "PROCESSING_STALE case_id=%s job_id=%s age_s=%s",
            case_id,
            job_id,
            int(age.total_seconds()),
        )
    return stale


def live_processing_status(case_id: str) -> dict | None:
    """Return the persisted job status with live elapsed + heartbeat stale detection.

    Terminal jobs (COMPLETED/FAILED/CANCELLED/STALE/INTERRUPTED) keep their final persisted elapsed value.
    """
    status = case_store.get_processing(case_id)
    if status is None:
        return None
    status = _mark_stale_if_needed(status)
    if status.get("stage_status") == "PROCESSING" and status.get("started_at"):
        status = {**status, "elapsed_seconds": _elapsed_seconds(status["started_at"])}
    from app.operation_history import remaining_time_for_case
    from engines.performance.remaining_time import estimate_remaining

    if status.get("stage_status") == "PROCESSING":
        remaining = remaining_time_for_case(case_id, status.get("elapsed_seconds"))
    else:
        remaining = estimate_remaining(
            (),
            elapsed_seconds=None,
            operation_id="case-processing",
            environment_id="",
            input_class="",
        )
    return {**status, "remaining_time": remaining}


def _status(
    case_id: str,
    job_id: str,
    *,
    current_stage: str,
    stage_status: str,
    overall_progress: int,
    stage_progress: int | None,
    completed: list[str],
    pending: list[str],
    error_state: bool = False,
    error_code: str | None = None,
    message: str = "",
    input_hash: str | None = None,
    created_at: str | None = None,
) -> dict:
    if stage_status not in STAGE_STATUSES:
        raise ValueError(f"Invalid stage_status: {stage_status}")
    current = case_store.get_processing(case_id) or {}
    # Guard: never write progress for a superseded job identity.
    if current.get("job_id") and current.get("job_id") != job_id and current.get("stage_status") == "PROCESSING":
        logger.warning(
            "PROCESSING_SUPERSEDED_WRITE_IGNORED case_id=%s write_job=%s active_job=%s",
            case_id,
            job_id,
            current.get("job_id"),
        )
        return current
    started_at = current.get("started_at") or _now()
    created = created_at or current.get("created_at") or started_at
    elapsed_seconds = _elapsed_seconds(started_at)
    arch = _derive_arch_statuses(current_stage, completed)
    payload = {
        "job_id": job_id,
        "case_id": case_id,
        "input_hash": input_hash if input_hash is not None else current.get("input_hash"),
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
        "created_at": created,
        "started_at": started_at,
        "updated_at": _now(),
        "heartbeat_at": _now(),
        "elapsed_seconds": elapsed_seconds,
        "upper_status": arch["upper_status"],
        "lower_status": arch["lower_status"],
        "planning_status": arch["planning_status"],
        "completed_at": _now()
        if stage_status in {"COMPLETED", "FAILED", "CANCELLED", "STALE", "INTERRUPTED"}
        else None,
        "result": "ok" if stage_status == "COMPLETED" else None,
    }
    case_store.set_processing(case_id, payload)
    if (
        stage_status == "COMPLETED"
        and current.get("job_id") == job_id
        and current.get("stage_status") != "COMPLETED"
        and elapsed_seconds > 0
    ):
        from app.operation_history import OPERATION_CASE_PROCESSING, input_class_for_case, record_completed_operation

        record_completed_operation(
            operation_id=OPERATION_CASE_PROCESSING,
            input_class=input_class_for_case(case_id),
            duration_seconds=elapsed_seconds,
        )
    logger.info(
        "PROCESSING_TRANSITION case_id=%s job_id=%s stage=%s status=%s progress=%s message=%s",
        case_id,
        job_id,
        current_stage,
        stage_status,
        payload["overall_progress"],
        message,
    )
    return payload


def _is_cancelled(job_id: str) -> bool:
    return job_id in _cancel_flags


def start_processing(case_id: str) -> dict:
    case = case_store.get(case_id)
    if case is None:
        raise KeyError("Case not found")
    with _lock:
        current = case_store.get_processing(case_id)
        if current:
            current = _mark_stale_if_needed(current)
        if current and current.get("stage_status") == "PROCESSING":
            # Duplicate-job protection: same identity, same progress — never invent a second job.
            return current
        input_hash = compute_case_input_hash(case_id)
        job_id = str(uuid4())
        created_at = _now()
        other_active = any(
            item.get("stage_status") == "PROCESSING"
            for existing_case in case_store.list()
            if existing_case.id != case_id
            for item in [case_store.get_processing(existing_case.id) or {}]
        )
        # New job identity always starts at 0% PREPARING — never inherits prior progress.
        initial = _status(
            case_id,
            job_id,
            current_stage="PREPARING",
            stage_status="PROCESSING",
            overall_progress=0,
            stage_progress=0,
            completed=[],
            pending=list(STAGES),
            message="Queued behind another case analysis" if other_active else "Analyzing case",
            input_hash=input_hash,
            created_at=created_at,
        )
        logger.info(
            "PROCESSING_CREATED case_id=%s job_id=%s input_hash=%s",
            case_id,
            job_id,
            input_hash[:12],
        )
        future = _executor.submit(_run, case_id, job_id)
        _active_futures[job_id] = future
        future.add_done_callback(lambda completed: _handle_worker_exit(case_id, job_id, completed))
        return initial


def cancel_processing(case_id: str) -> dict:
    """Request cooperative cancellation of the active PROCESSING job.

    Cancellation is a durable terminal state. Partial segmentation marked
    ``processing`` is demoted to ``cancelled`` so it is never treated as
    current clinical truth. Does not report COMPLETED.
    """
    with _lock:
        current = case_store.get_processing(case_id)
        if current is None:
            raise KeyError("No processing job")
        if current.get("stage_status") != "PROCESSING":
            return current
        job_id = current["job_id"]
        _cancel_flags.add(job_id)
        # Best-effort: stop WP-12 isolated validation workers for this process.
        try:
            from engines.validation.isolated_execution import cancel_validation_work

            cancel_validation_work()
        except Exception:  # noqa: BLE001 - cancel path must stay best-effort
            pass
        case = case_store.get(case_id)
        if case is not None:
            seg = getattr(case, "segmentation_results", None)
            if isinstance(seg, dict) and seg.get("status") == "processing":
                seg = {**seg, "status": "cancelled", "error": "Segmentation cancelled by user"}
                setattr(case, "segmentation_results", seg)
                case_store.update(case)
        return _status(
            case_id,
            job_id,
            current_stage=current.get("current_stage", "PREPARING"),
            stage_status="CANCELLED",
            overall_progress=current.get("overall_progress", 0),
            stage_progress=current.get("stage_progress"),
            completed=list(current.get("completed_stages") or []),
            pending=[stage for stage in STAGES if stage not in (current.get("completed_stages") or [])],
            error_state=False,
            error_code="CANCELLED",
            message="Case analysis was cancelled",
            input_hash=current.get("input_hash"),
            created_at=current.get("created_at"),
        )


def _handle_worker_exit(case_id: str, job_id: str, future: Future[None]) -> None:
    _active_futures.pop(job_id, None)
    try:
        error = future.exception()
    except BaseException as worker_exit:
        error = worker_exit
    if error is None:
        _cancel_flags.discard(job_id)
        return
    logger.error(
        "PROCESSING_WORKER_EXITED case_id=%s job_id=%s error=%s",
        case_id,
        job_id,
        error,
    )
    current = case_store.get_processing(case_id) or {}
    if current.get("job_id") != job_id or current.get("stage_status") != "PROCESSING":
        _cancel_flags.discard(job_id)
        return
    _fail(
        case_id,
        job_id,
        current.get("completed_stages", []),
        "Processing could not be completed for this case",
        f"{type(error).__name__}: {error}",
    )
    _cancel_flags.discard(job_id)


def _run(case_id: str, job_id: str) -> None:
    completed: list[str] = []
    try:
        if _is_cancelled(job_id):
            return
        # PREPARING → complete before validation (truthful lifecycle; never skip identity).
        completed.append("PREPARING")
        _status(
            case_id,
            job_id,
            current_stage="VALIDATING_SCANS",
            stage_status="PROCESSING",
            overall_progress=5,
            stage_progress=100,
            completed=completed,
            pending=[stage for stage in STAGES if stage not in completed],
            message="Validating scans",
        )
        case = case_store.get(case_id)
        if case is None:
            raise KeyError("Case not found")
        if {mesh.arch for mesh in case.meshes} != {"upper", "lower"}:
            raise ValueError("Both upper and lower scans are required before processing")
        if _is_cancelled(job_id):
            return
        completed.append("VALIDATING_SCANS")
        from app.processing_modes import ProcessingModeError, resolve_processing_mode
        from app.segmentation_store import (
            begin_segmentation_record,
            complete_segmentation_record,
            store_arch_result,
        )
        from app.plan_from_pipeline import generate_plan_from_arch_diagnostics

        current_status = case_store.get_processing(case_id) or {}
        input_hash = current_status.get("input_hash") or compute_case_input_hash(case_id)
        try:
            mode = resolve_processing_mode()
        except ProcessingModeError as error:
            raise ValueError(str(error)) from error

        begin_segmentation_record(
            case_id,
            job_id=job_id,
            input_hash=input_hash,
            processing_mode=mode.value,
        )
        # Both arches segment in parallel — report SEGMENTING_BOTH, never pretend lower waits.
        _status(
            case_id,
            job_id,
            current_stage="SEGMENTING_BOTH",
            stage_status="PROCESSING",
            overall_progress=10,
            stage_progress=None,
            completed=completed,
            pending=[stage for stage in STAGES if stage not in completed],
            message="Segmenting upper and lower arches",
            input_hash=input_hash,
        )
        upper_path = next(m.file_path for m in case.meshes if m.arch == "upper")
        lower_path = next(m.file_path for m in case.meshes if m.arch == "lower")
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                "SEGMENTING_UPPER": pool.submit(
                    process_uploaded_case,
                    upper_path,
                    ArchType.UPPER,
                    case_id=case_id,
                    job_id=job_id,
                    input_hash=input_hash,
                    processing_mode=mode.value,
                ),
                "SEGMENTING_LOWER": pool.submit(
                    process_uploaded_case,
                    lower_path,
                    ArchType.LOWER,
                    case_id=case_id,
                    job_id=job_id,
                    input_hash=input_hash,
                    processing_mode=mode.value,
                ),
            }
            pending_futures = set(futures.values())
            upper = lower = None
            while pending_futures:
                if _is_cancelled(job_id):
                    for future in pending_futures:
                        future.cancel()
                    return
                done, pending_futures = wait(pending_futures, timeout=1.0, return_when=FIRST_COMPLETED)
                # Heartbeat while waiting so hung segmentation does not look like a live READY jump.
                if not done:
                    current = case_store.get_processing(case_id) or {}
                    if current.get("job_id") == job_id and current.get("stage_status") == "PROCESSING":
                        current["heartbeat_at"] = _now()
                        current["updated_at"] = _now()
                        case_store.set_processing(case_id, current)
                    continue
                for stage_name, future in futures.items():
                    if future in done and stage_name not in completed:
                        result = future.result()
                        arch_name = "upper" if stage_name == "SEGMENTING_UPPER" else "lower"
                        if stage_name == "SEGMENTING_UPPER":
                            upper = result
                        else:
                            lower = result
                        store_arch_result(
                            case_id,
                            arch_name,
                            result.payload(),
                            model_name=result.model_name,
                            model_version=result.model_version,
                            segment_ms=result.segmentation_runtime_ms,
                        )
                        completed.append(stage_name)
                        progress = 10 + int(45 * (len([s for s in completed if s.startswith("SEGMENTING")]) / 2))
                        remaining_seg = [
                            s for s in ("SEGMENTING_UPPER", "SEGMENTING_LOWER") if s not in completed
                        ]
                        stage_label = remaining_seg[0] if remaining_seg else "SEGMENTING_BOTH"
                        _status(
                            case_id,
                            job_id,
                            current_stage=stage_label if remaining_seg else "SEGMENTING_BOTH",
                            stage_status="PROCESSING",
                            overall_progress=progress,
                            stage_progress=None,
                            completed=completed,
                            pending=[stage for stage in STAGES if stage not in completed],
                            message=(
                                "Segmenting lower arch"
                                if remaining_seg == ["SEGMENTING_LOWER"]
                                else "Segmenting upper arch"
                                if remaining_seg == ["SEGMENTING_UPPER"]
                                else "Segmentation complete"
                            ),
                            input_hash=input_hash,
                        )
        if upper is None or lower is None:
            raise RuntimeError("Segmentation futures completed without results")
        if _is_cancelled(job_id):
            return
        failed_states = SEGMENTATION_FAILURE_STATES
        reviewable = {"identification_incomplete", "planning_ready"}
        if upper.state.value in failed_states or lower.state.value in failed_states:
            complete_segmentation_record(
                case_id,
                status="failed",
                error="; ".join(
                    list(upper.failures) + list(lower.failures)
                ) or "Segmentation failed",
            )
            raise ValueError(
                "; ".join(list(upper.failures) + list(lower.failures))
                or "Real segmentation failed without fixture substitution"
            )
        if upper.state.value not in reviewable or lower.state.value not in reviewable:
            complete_segmentation_record(
                case_id,
                status="failed",
                error="Segmentation completed without a reviewable identification result",
            )
            raise ValueError("Segmentation completed without a reviewable identification result")
        persist_started = perf_counter()
        from app.failure_injection import maybe_fail

        maybe_fail("after_segmentation_output")
        complete_segmentation_record(case_id, status="completed", persist_ms=(perf_counter() - persist_started) * 1000)
        # WP-02: Dental Intelligence 2.0 from genuine persisted segmentation — never unlocks treatment.
        try:
            from app.intelligence_store import build_and_store_dental_intelligence

            build_and_store_dental_intelligence(case_id)
        except Exception as intel_error:  # noqa: BLE001 - intelligence must not crash processing
            logger.warning(
                "DENTAL_INTELLIGENCE_BUILD_FAILED case_id=%s job_id=%s error=%s",
                case_id,
                job_id,
                intel_error,
            )
        _status(
            case_id,
            job_id,
            current_stage="BUILDING_PLAN",
            stage_status="PROCESSING",
            overall_progress=70,
            stage_progress=None,
            completed=completed,
            pending=[stage for stage in STAGES if stage not in completed],
            message="Preparing treatment setup",
            input_hash=input_hash,
        )

        def _report_planning_progress(progress: int, message: str) -> None:
            if _is_cancelled(job_id):
                return
            # Clamp planning callbacks into BUILDING_PLAN band (70–87). Never jump from idle/ready.
            clamped = max(70, min(87, progress))
            _status(
                case_id,
                job_id,
                current_stage="BUILDING_PLAN",
                stage_status="PROCESSING",
                overall_progress=clamped,
                stage_progress=None,
                completed=completed,
                pending=[stage for stage in STAGES if stage not in completed],
                message=message,
                input_hash=input_hash,
            )

        planning_started = perf_counter()
        logger.info("PLAN_BUILDING_STARTED case_id=%s job_id=%s", case_id, job_id)
        generate_plan_from_arch_diagnostics(
            case_id, upper, lower, progress_callback=_report_planning_progress
        )
        if _is_cancelled(job_id):
            return
        logger.info(
            "PLAN_BUILDING_COMPLETED case_id=%s job_id=%s duration_ms=%.0f",
            case_id,
            job_id,
            (perf_counter() - planning_started) * 1000,
        )
        completed.append("BUILDING_PLAN")
        # Validation already ran inside plan compose; this stage records that completed work.
        _status(
            case_id,
            job_id,
            current_stage="VALIDATING_PLAN",
            stage_status="PROCESSING",
            overall_progress=88,
            stage_progress=100,
            completed=completed,
            pending=[stage for stage in STAGES if stage not in completed],
            message="Recording geometric validation results",
            input_hash=input_hash,
        )
        completed.append("VALIDATING_PLAN")
        _status(
            case_id,
            job_id,
            current_stage="FINALIZING",
            stage_status="PROCESSING",
            overall_progress=96,
            stage_progress=100,
            completed=completed,
            pending=[],
            message="Finalizing workspace",
            input_hash=input_hash,
        )
        completed.append("FINALIZING")
        _status(
            case_id,
            job_id,
            current_stage="FINALIZING",
            stage_status="COMPLETED",
            overall_progress=100,
            stage_progress=100,
            completed=completed,
            pending=[],
            message="Case ready",
            input_hash=input_hash,
        )

    except HTTPException as error:
        if not _is_cancelled(job_id):
            _fail(case_id, job_id, completed, str(error.detail), f"HTTP_{error.status_code}")
    except Exception as error:
        if not _is_cancelled(job_id):
            _fail(
                case_id,
                job_id,
                completed,
                "Processing could not be completed for this case",
                str(error),
            )


def _fail(case_id: str, job_id: str, completed: list[str], message: str, diagnostic: str) -> None:
    current = case_store.get_processing(case_id) or {}
    current["technical_diagnostic"] = diagnostic
    case_store.set_processing(case_id, current)
    _status(
        case_id,
        job_id,
        current_stage=current.get("current_stage", "PREPARING"),
        stage_status="FAILED",
        overall_progress=current.get("overall_progress", 0),
        stage_progress=current.get("stage_progress"),
        completed=completed,
        pending=[stage for stage in STAGES if stage not in completed],
        error_state=True,
        error_code="PROCESSING_FAILED",
        message=message,
        input_hash=current.get("input_hash"),
        created_at=current.get("created_at"),
    )
