"""FV-02.1 / FV-02.2 preparation contract.

Preparation readiness is a technical gate for a later processing step.
It is not clinical segmentation, clinical orientation, FDI, or occlusion.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Any


class PreparationReadiness(StrEnum):
    NOT_PREPARED = "NOT_PREPARED"
    PREPARED = "PREPARED"
    READY_FOR_SEGMENTATION = "READY_FOR_SEGMENTATION"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"


class PreparationJobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


PREPARATION_READINESS_VALUES = frozenset(item.value for item in PreparationReadiness)
TERMINAL_PREPARATION_JOB_STATES = frozenset(
    {
        PreparationJobState.COMPLETED.value,
        PreparationJobState.FAILED.value,
        PreparationJobState.CANCELLED.value,
    }
)
ACTIVE_PREPARATION_JOB_STATES = frozenset(
    {PreparationJobState.QUEUED.value, PreparationJobState.RUNNING.value}
)


def preparation_readiness(
    *,
    operation_count: int,
    blockers: list[str],
    warnings: list[str],
    accepted: bool,
) -> str:
    """Map rechecked quality to a preparation state.

    Acceptance is an explicit user step. Geometry edits clear it.
    """
    if blockers:
        return PreparationReadiness.BLOCKED.value
    if not accepted:
        if operation_count == 0:
            return PreparationReadiness.NOT_PREPARED.value
        return PreparationReadiness.PREPARED.value
    if warnings:
        return PreparationReadiness.READY_WITH_WARNINGS.value
    return PreparationReadiness.READY_FOR_SEGMENTATION.value


def future_segmentation_input(
    *,
    source_sha256: str | None,
    prepared_sha256: str | None,
    uses_prepared_mesh: bool,
    technical_gate_passed: bool = False,
) -> dict[str, Any]:
    """Point at a later segmentation input without replacing the source hash."""
    return {
        "role": "FUTURE_SEGMENTATION_INPUT",
        "source_sha256": source_sha256,
        "prepared_sha256": prepared_sha256,
        "uses_prepared_mesh": uses_prepared_mesh,
        "uses_derived_hash_as_source": False,
        "clinically_segmented": False,
        "fdi_assigned": False,
        "occlusion_established": False,
        "clinical_axes": False,
        "technical_gate_passed": technical_gate_passed,
        "clinically_ready": False,
    }


def empty_preparation(artifact: dict[str, Any]) -> dict[str, Any]:
    source_sha = artifact.get("sha256")
    return {
        "readiness": PreparationReadiness.NOT_PREPARED.value,
        "version": 0,
        "accepted": False,
        "operations": [],
        "versions": [],
        "lineage": [],
        "jobs": [],
        "provenance_events": [],
        "commit_generation": 0,
        "active": None,
        "source_artifact_id": artifact.get("artifact_id"),
        "source_sha256": source_sha,
        "clinically_segmented": False,
        "fdi_assigned": False,
        "occlusion_established": False,
        "bite_registration_established": False,
        "clinical_axes": False,
        "future_segmentation_input": future_segmentation_input(
            source_sha256=source_sha,
            prepared_sha256=None,
            uses_prepared_mesh=False,
        ),
        "quality_comparison": None,
        "components": [],
        "camera_note": (
            "Standard views and fit are existing viewport commands. "
            "They do not change source coordinates."
        ),
    }


def _normalize_preparation_value(value: Any) -> Any:
    """Stable cache material. Bool stays bool. Numbers become finite floats."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Preparation parameters must be finite.")
        return round(number, 9)
    if isinstance(value, (list, tuple)):
        return [_normalize_preparation_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _normalize_preparation_value(value[key]) for key in sorted(value, key=str)
        }
    raise ValueError(f"Unsupported preparation value: {type(value).__name__}")


def normalize_preparation_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_preparation_value(parameters)
    if not isinstance(normalized, dict):
        raise ValueError("Preparation parameters must be an object.")
    return normalized


def preparation_cache_key(
    *,
    source_sha256: str,
    operation: str,
    parameters: dict[str, Any],
    algorithm: str,
    algorithm_version: str,
    replay_prefix: list[dict[str, Any]],
) -> str:
    """Identity of one derived step.

    The replay prefix is included so the same trim is not reused after a
    different orientation. A different source hash cannot hit.
    """
    body = {
        "source_sha256": source_sha256,
        "operation": operation,
        "parameters": normalize_preparation_parameters(parameters),
        "algorithm": algorithm,
        "algorithm_version": algorithm_version,
        "replay_prefix": _normalize_preparation_value(replay_prefix),
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def operation_algorithm(operation: str, parameters: dict[str, Any]) -> str:
    if operation == "orient":
        method = str(parameters.get("method") or "user_transform")
        if method == "vertex_pca":
            return "vertex_pca_alignment"
        if method == "user_transform":
            return "user_rigid_transform"
        raise ValueError("Orientation method must be user_transform or vertex_pca.")
    if operation == "trim":
        return "centroid_region_crop"
    if operation == "cleanup":
        return "trimesh_safe_cleanup"
    if operation == "components":
        return "remove_selected_components"
    raise ValueError("Operation must be orient, trim, cleanup, or components.")


def lineage_gaps(session: dict[str, Any]) -> list[str]:
    """The active lineage entry must explain the current operation chain."""
    operations = list(session.get("operations") or [])
    if not operations:
        return []
    active_lineage = None
    for item in reversed(session.get("lineage") or []):
        if item.get("lifecycle") == "active" and item.get("output_sha256"):
            active_lineage = item
            break
    if active_lineage is None:
        return ["lineage_missing"]
    reasons: list[str] = []
    recorded = list(active_lineage.get("operations") or [])
    if len(recorded) != len(operations):
        reasons.append("lineage_incomplete")
    else:
        for left, right in zip(recorded, operations, strict=True):
            if left.get("operation") != right.get("operation"):
                reasons.append("lineage_operation_mismatch")
            if not left.get("algorithm") or not left.get("algorithm_version"):
                reasons.append("lineage_algorithm_missing")
    if active_lineage.get("source_sha256") != session.get("source_sha256"):
        reasons.append("lineage_source_mismatch")
    active = session.get("active") or {}
    if active_lineage.get("output_sha256") != active.get("output_sha256"):
        reasons.append("lineage_output_mismatch")
    if not active_lineage.get("source_artifact_id"):
        reasons.append("lineage_source_artifact_missing")
    return list(dict.fromkeys(reasons))


def failed_job_reference(session: dict[str, Any]) -> list[str]:
    """A failed or cancelled job must not be the active prepared input."""
    active = session.get("active") or {}
    if not active:
        return []
    reasons: list[str] = []
    active_job = active.get("job_id")
    for job in session.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        state = job.get("state")
        if state not in {PreparationJobState.FAILED.value, PreparationJobState.CANCELLED.value}:
            continue
        referenced = False
        if active_job and job.get("job_id") == active_job:
            referenced = True
        output = job.get("output_artifact_hash")
        if output and output == active.get("output_sha256") and job.get("published") is True:
            referenced = True
        if referenced:
            reasons.append("failed_or_cancelled_job_referenced")
    if active_job:
        match = next(
            (job for job in session.get("jobs") or [] if job.get("job_id") == active_job),
            None,
        )
        if match is not None and match.get("state") != PreparationJobState.COMPLETED.value:
            reasons.append("active_job_not_completed")
    return list(dict.fromkeys(reasons))


def structural_preparation_gate(
    session: dict[str, Any] | None, artifact_sha256: str | None
) -> list[str]:
    """Data checks that do not load a mesh."""
    reasons: list[str] = []
    current = session or {}
    readiness = current.get("readiness")
    if readiness not in PREPARATION_READINESS_VALUES:
        reasons.append("invalid_preparation_state")
    if current.get("source_sha256") != artifact_sha256:
        reasons.append("provenance_source_hash_mismatch")
    operations = list(current.get("operations") or [])
    active = current.get("active") or None
    if operations:
        if not isinstance(active, dict) or not active.get("output_sha256"):
            reasons.append("missing_derived_hash")
        elif active.get("source_sha256") != artifact_sha256:
            reasons.append("derived_provenance_mismatch")
        reasons.extend(lineage_gaps(current))
        comparison = (current.get("quality_comparison") or {}).get("prepared") or {}
        if not comparison:
            reasons.append("quality_missing")
        else:
            blockers = list(comparison.get("blockers") or [])
            if any("finite" in str(item) for item in blockers):
                reasons.append("geometry_not_finite")
            faces = comparison.get("face_count")
            vertices = comparison.get("vertex_count")
            if not isinstance(faces, int) or faces <= 0:
                reasons.append("face_count_inconsistent")
            if not isinstance(vertices, int) or vertices <= 0:
                reasons.append("vertex_count_inconsistent")
    reasons.extend(failed_job_reference(current))
    return list(dict.fromkeys(reasons))
