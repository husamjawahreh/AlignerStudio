"""Persist Dental Intelligence 2.0 documents bound to case/job/input identity (WP-02)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.segmentation_store import get_segmentation_record
from app.store import case_store
from engines.arrangement.dental_intelligence import build_case_dental_intelligence


def get_dental_intelligence_record(case_id: str) -> dict[str, Any] | None:
    case = case_store.get(case_id)
    if case is None:
        return None
    record = getattr(case, "dental_intelligence", None)
    return deepcopy(record) if isinstance(record, dict) else None


def clear_dental_intelligence_record(case_id: str) -> None:
    case = case_store.get(case_id)
    if case is None:
        return
    setattr(case, "dental_intelligence", None)
    case_store.update(case)


def store_dental_intelligence_record(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    case = case_store.get(case_id)
    if case is None:
        raise KeyError(f"Case {case_id} is not present")
    setattr(case, "dental_intelligence", payload)
    case_store.update(case)
    return deepcopy(payload)


def build_and_store_dental_intelligence(case_id: str) -> dict[str, Any]:
    """Build Dental Intelligence 2.0 from the completed WP-01 segmentation record."""
    segmentation = get_segmentation_record(case_id)
    if segmentation is None:
        raise ValueError("No segmentation record available for dental intelligence")
    if segmentation.get("status") != "completed":
        raise ValueError(
            f"Segmentation status is {segmentation.get('status')!r}; "
            "completed results are required for dental intelligence"
        )
    intelligence = build_case_dental_intelligence(
        case_id=case_id,
        segmentation_record=segmentation,
    )
    return store_dental_intelligence_record(case_id, intelligence.payload())
