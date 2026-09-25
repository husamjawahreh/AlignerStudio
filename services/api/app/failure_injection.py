"""Test-only failure injection for WP-13 reliability proofs.

Enabled only when ALIGNERSTUDIO_FAILURE_INJECTION=1 (never default-on).
Points are named strings; each may fire once per process unless reset.

Never use these hooks to fabricate clinical success — they only raise
controlled failures so persistence integrity can be proven.
"""

from __future__ import annotations

import os
from threading import Lock

_lock = Lock()
_fired: set[str] = set()

# Known injection points (document in WP13_RELIABILITY.md).
POINTS = frozenset(
    {
        "after_upload_persist",
        "after_segmentation_output",
        "before_validation_complete",
        "after_validation_persist",
        "before_production_complete",
        "during_export",
        "before_case_store_persist",
    }
)


def injection_enabled() -> bool:
    return os.environ.get("ALIGNERSTUDIO_FAILURE_INJECTION", "").strip() in {
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    }


def reset_failure_injection() -> None:
    """Clear fired set and configured points (tests)."""
    with _lock:
        _fired.clear()
    os.environ.pop("ALIGNERSTUDIO_FAIL_AT", None)


def configure_failure_point(point: str) -> None:
    """Arm a single failure point. Requires ALIGNERSTUDIO_FAILURE_INJECTION=1."""
    if point not in POINTS:
        raise ValueError(f"Unknown failure injection point: {point}")
    os.environ["ALIGNERSTUDIO_FAIL_AT"] = point
    with _lock:
        _fired.discard(point)


def maybe_fail(point: str) -> None:
    """Raise RuntimeError once if this point is armed and injection is enabled."""
    if not injection_enabled():
        return
    armed = os.environ.get("ALIGNERSTUDIO_FAIL_AT", "").strip()
    if armed != point:
        return
    with _lock:
        if point in _fired:
            return
        _fired.add(point)
    raise RuntimeError(f"ALIGNERSTUDIO_FAILURE_INJECTION:{point}")


__all__ = [
    "POINTS",
    "configure_failure_point",
    "injection_enabled",
    "maybe_fail",
    "reset_failure_injection",
]
