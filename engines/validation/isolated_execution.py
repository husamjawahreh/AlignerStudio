"""Process-isolated GeometricValidationEngine execution (WP-12 / WP-13).

Long geometric validation is CPU-bound Python/numpy work that holds the GIL
for minutes on real dual-arch cases. When it runs inside the API process
(even on a ThreadPoolExecutor worker), sync FastAPI handlers and status
polling starve.

This module runs the *same* GeometricValidationEngine.validate() in a
dedicated worker process so the API process stays responsive. Clinical
semantics, thresholds, and report structure are unchanged.

Environment:
  ALIGNERSTUDIO_VALIDATION_PROCESS_ISOLATION
    "1" (default) — run validate in a process pool worker
    "0" — in-process (legacy / debugging)

Case isolation: the pool is process-local; staging payloads are passed
explicitly per call (no shared mutable clinical cache across cases).
WP-13: cancel_validation_work() best-effort cancels in-flight futures.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
from concurrent.futures import Future, ProcessPoolExecutor
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.treatment_plan.staging import StagingResult
    from domain.treatment_plan.validation import TreatmentValidationReport
    from engines.validation.geometric_engine import GeometricValidationConfiguration

logger = logging.getLogger(__name__)

_pool: ProcessPoolExecutor | None = None
_pool_lock = Lock()
_POOL_WORKERS = 1
_active_futures: set[Future] = set()


def _isolation_enabled() -> bool:
    configured = os.environ.get("ALIGNERSTUDIO_VALIDATION_PROCESS_ISOLATION", "1")
    return configured.strip() not in {"0", "false", "False", "no", "NO"}


def _validate_worker(
    staging: "StagingResult",
    configuration: "GeometricValidationConfiguration",
) -> "TreatmentValidationReport":
    """Top-level picklable worker — must stay importable under spawn."""
    from engines.validation.geometric_engine import GeometricValidationEngine

    return GeometricValidationEngine().validate(staging, configuration)


def _get_pool() -> ProcessPoolExecutor:
    global _pool
    with _pool_lock:
        if _pool is None:
            # spawn avoids fork-from-threaded-parent deadlocks (API uses threads).
            ctx = mp.get_context("spawn")
            _pool = ProcessPoolExecutor(
                max_workers=_POOL_WORKERS,
                mp_context=ctx,
            )
            logger.info(
                "GEOMETRIC_VALIDATION_PROCESS_POOL_STARTED workers=%d context=spawn",
                _POOL_WORKERS,
            )
        return _pool


def cancel_validation_work() -> None:
    """Best-effort cancel of in-flight isolated validation futures (WP-13)."""
    with _pool_lock:
        pending = list(_active_futures)
        for future in pending:
            future.cancel()
        _active_futures.clear()
        # Recreate pool so a cancelled worker cannot deliver a late report as current.
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
            globals()["_pool"] = None
            logger.info("GEOMETRIC_VALIDATION_PROCESS_POOL_CANCELLED")


def shutdown_validation_pool() -> None:
    """Release the process pool (tests / orderly shutdown)."""
    global _pool
    with _pool_lock:
        _active_futures.clear()
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=False)
            _pool = None


def validate_staging(
    staging: "StagingResult",
    configuration: "GeometricValidationConfiguration",
) -> "TreatmentValidationReport":
    """Validate staging with optional process isolation. Semantics identical either path."""
    from app.failure_injection import maybe_fail
    from engines.validation.geometric_engine import GeometricValidationEngine

    maybe_fail("before_validation_complete")

    if not _isolation_enabled():
        report = GeometricValidationEngine().validate(staging, configuration)
        maybe_fail("after_validation_persist")
        return report

    pool = _get_pool()
    future = pool.submit(_validate_worker, staging, configuration)
    with _pool_lock:
        _active_futures.add(future)
    try:
        report = future.result()
    finally:
        with _pool_lock:
            _active_futures.discard(future)
    logger.info(
        "GEOMETRIC_VALIDATION_ISOLATED_COMPLETED plan_id=%s report_id=%s status=%s",
        staging.plan_id,
        report.report_id,
        report.status.value,
    )
    maybe_fail("after_validation_persist")
    return report


__all__ = [
    "cancel_validation_work",
    "shutdown_validation_pool",
    "validate_staging",
]
