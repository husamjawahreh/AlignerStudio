"""Bounded history of completed operation durations on this computer.

Stores operation class, input class, and duration. Does not store meshes,
scans, tooth identities, or patient references. Samples from another
environment id are ignored by the estimator.
"""

from __future__ import annotations

import json
import os
from threading import Lock

from engines.performance.remaining_time import environment_id, estimate_remaining

OPERATION_CASE_PROCESSING = "case-processing"
_MAX_SAMPLES = 48
_lock = Lock()
_samples: list[dict] = []
_loaded = False


def _history_path():
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    from app.config import CASE_STORE_PATH

    return CASE_STORE_PATH.with_name("operation_history.json")


def clear_operation_history() -> None:
    global _loaded
    with _lock:
        _samples.clear()
        _loaded = True


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    path = _history_path()
    _loaded = True
    if path is None or not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    rows = payload.get("samples") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return
    for row in rows[-_MAX_SAMPLES:]:
        if not isinstance(row, dict):
            continue
        duration = row.get("duration_seconds")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
            continue
        _samples.append(
            {
                "operation_id": str(row.get("operation_id") or ""),
                "environment_id": str(row.get("environment_id") or ""),
                "input_class": str(row.get("input_class") or "unknown"),
                "duration_seconds": float(duration),
            }
        )


def _persist_locked() -> None:
    path = _history_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps({"samples": _samples[-_MAX_SAMPLES:]}, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def record_completed_operation(
    *,
    operation_id: str,
    input_class: str,
    duration_seconds: float,
) -> None:
    """Record one finished run. Cancelled and failed runs are not durations."""
    if duration_seconds <= 0:
        return
    with _lock:
        _ensure_loaded()
        _samples.append(
            {
                "operation_id": operation_id,
                "environment_id": environment_id(),
                "input_class": input_class or "unknown",
                "duration_seconds": float(duration_seconds),
            }
        )
        del _samples[:-_MAX_SAMPLES]
        _persist_locked()


def samples_snapshot() -> tuple[dict, ...]:
    with _lock:
        _ensure_loaded()
        return tuple(dict(item) for item in _samples)


def input_class_for_case(case_id: str) -> str:
    from app.store import case_store

    case = case_store.get(case_id)
    if case is None:
        return "unknown"
    arches = sorted({getattr(mesh, "arch", None) for mesh in getattr(case, "meshes", ())})
    arches = [arch for arch in arches if arch]
    if set(arches) == {"upper", "lower"}:
        return "both-arches"
    if arches == ["upper"]:
        return "upper-only"
    if arches == ["lower"]:
        return "lower-only"
    return "unknown"


def remaining_time_for_case(case_id: str, elapsed_seconds: float | None) -> dict:
    input_class = input_class_for_case(case_id)
    with _lock:
        _ensure_loaded()
        samples = tuple(_samples)
    return estimate_remaining(
        samples,
        elapsed_seconds=elapsed_seconds,
        operation_id=OPERATION_CASE_PROCESSING,
        environment_id=environment_id(),
        input_class=input_class,
    )
