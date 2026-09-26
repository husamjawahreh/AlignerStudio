"""Durable segmentation result records bound to case/job/input identity (WP-01)."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from domain.tooth.segmentation_proof import (
    SegmentationProofError,
    refuse_fixture_on_real_record,
)

from app.store import case_store


def _now() -> str:
    return datetime.now(UTC).isoformat()


def get_segmentation_record(case_id: str) -> dict[str, Any] | None:
    case = case_store.get(case_id)
    if case is None:
        return None
    record = getattr(case, "segmentation_results", None)
    return deepcopy(record) if isinstance(record, dict) else None


def clear_segmentation_record(case_id: str) -> None:
    case = case_store.get(case_id)
    if case is None:
        return
    case.segmentation_results = None
    case_store.update(case)


def begin_segmentation_record(
    case_id: str,
    *,
    job_id: str,
    input_hash: str,
    processing_mode: str,
) -> dict[str, Any]:
    record = {
        "case_id": case_id,
        "job_id": job_id,
        "input_hash": input_hash,
        "processing_mode": processing_mode,
        "created_at": _now(),
        "updated_at": _now(),
        "model_name": None,
        "model_version": None,
        "status": "processing",
        "arches": {},
        "timings_ms": {
            "preprocess_upper": None,
            "preprocess_lower": None,
            "segment_upper": None,
            "segment_lower": None,
            "persist": None,
            "total": None,
        },
        "error": None,
    }
    case = case_store.get(case_id)
    if case is None:
        raise KeyError(f"Case {case_id} is not present")
    case.segmentation_results = record
    case_store.update(case)
    return deepcopy(record)


def store_arch_result(
    case_id: str,
    arch: str,
    payload: dict[str, Any],
    *,
    model_name: str | None = None,
    model_version: str | None = None,
    segment_ms: float | None = None,
    preprocess_ms: float | None = None,
) -> dict[str, Any]:
    case = case_store.get(case_id)
    if case is None:
        raise KeyError(f"Case {case_id} is not present")
    record = getattr(case, "segmentation_results", None)
    if not isinstance(record, dict):
        raise KeyError(f"No segmentation record for case {case_id}")
    try:
        refuse_fixture_on_real_record(
            processing_mode=record.get("processing_mode"),
            payload=payload,
        )
    except SegmentationProofError as error:
        raise ValueError(str(error)) from error
    contract = payload.get("segmentation_contract") or {}
    source_hash = payload.get("source_mesh_sha256")
    if (
        contract.get("source_mesh_hash")
        and source_hash
        and contract["source_mesh_hash"] != source_hash
    ):
        raise ValueError(
            "Refusing to persist a segmentation whose source hash does not match the upload."
        )
    if (
        contract.get("case_input_hash")
        and record.get("input_hash")
        and contract["case_input_hash"] != record["input_hash"]
    ):
        raise ValueError(
            "Refusing to persist a segmentation whose input hash does not match the case."
        )
    arches = dict(record.get("arches") or {})
    arches[arch] = {
        **payload,
        "stored_at": _now(),
        "source_mesh_path": payload.get("source_mesh_path"),
        "source_mesh_sha256": payload.get("source_mesh_sha256"),
    }
    record["arches"] = arches
    record["updated_at"] = _now()
    if model_name:
        record["model_name"] = model_name
    if model_version:
        record["model_version"] = model_version
    timings = dict(record.get("timings_ms") or {})
    if segment_ms is not None:
        timings[f"segment_{arch}"] = segment_ms
    if preprocess_ms is not None:
        timings[f"preprocess_{arch}"] = preprocess_ms
    record["timings_ms"] = timings
    case.segmentation_results = record
    case_store.update(case)
    return deepcopy(record)


def complete_segmentation_record(
    case_id: str,
    *,
    status: str = "completed",
    error: str | None = None,
    total_ms: float | None = None,
    persist_ms: float | None = None,
) -> dict[str, Any]:
    case = case_store.get(case_id)
    if case is None:
        raise KeyError(f"Case {case_id} is not present")
    record = getattr(case, "segmentation_results", None)
    if not isinstance(record, dict):
        raise KeyError(f"No segmentation record for case {case_id}")
    record["status"] = status
    record["error"] = error
    record["updated_at"] = _now()
    record["completed_at"] = _now()
    timings = dict(record.get("timings_ms") or {})
    if total_ms is not None:
        timings["total"] = total_ms
    if persist_ms is not None:
        timings["persist"] = persist_ms
    record["timings_ms"] = timings
    case.segmentation_results = record
    case_store.update(case)
    return deepcopy(record)
