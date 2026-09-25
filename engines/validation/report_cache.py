"""Provenance-keyed validation report reuse (WP-12 / WP-13).

Caches TreatmentValidationReport by explicit clinical bindings:
  plan_id (embeds case_id) + staging_id + engine_version + thresholds

Never shares across cases: plan_id is case-bound in TreatmentPlanningEngine.
Invalidation is implicit — a new staging_id / plan_id means a miss.

Bounded LRU prevents unbounded growth under repeated edits.
"""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.treatment_plan.staging import StagingResult
    from domain.treatment_plan.validation import TreatmentValidationReport
    from engines.validation.geometric_engine import GeometricValidationConfiguration

_MAX_ENTRIES = 32
_lock = Lock()
_cache: OrderedDict[str, "TreatmentValidationReport"] = OrderedDict()


def _cache_key(
    staging: "StagingResult",
    configuration: "GeometricValidationConfiguration",
) -> str:
    # plan_id includes case_id — explicit case isolation for WP-13.
    return (
        f"{staging.plan_id}|{staging.staging_id}|{configuration.engine_version}|"
        f"{configuration.proximity_threshold}|{configuration.contact_tolerance}|"
        f"{configuration.collision_tolerance}"
    )


def get_cached_report(
    staging: "StagingResult",
    configuration: "GeometricValidationConfiguration",
) -> "TreatmentValidationReport | None":
    key = _cache_key(staging, configuration)
    with _lock:
        report = _cache.get(key)
        if report is None:
            return None
        _cache.move_to_end(key)
        return report


def store_cached_report(
    staging: "StagingResult",
    configuration: "GeometricValidationConfiguration",
    report: "TreatmentValidationReport",
) -> None:
    key = _cache_key(staging, configuration)
    with _lock:
        _cache[key] = report
        _cache.move_to_end(key)
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)


def clear_validation_report_cache() -> None:
    with _lock:
        _cache.clear()


def cache_snapshot_keys() -> tuple[str, ...]:
    """Test helper — inspect keys without exposing report payloads."""
    with _lock:
        return tuple(_cache.keys())


__all__ = [
    "cache_snapshot_keys",
    "clear_validation_report_cache",
    "get_cached_report",
    "store_cached_report",
]
