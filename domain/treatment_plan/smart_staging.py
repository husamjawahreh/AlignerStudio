"""Smart Staging Engine contracts (WP-06).

Wraps Phase-6 deterministic linear staging with setup-version binding,
truth states, readiness, and stale detection. Never claims clinical optimality.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


ALGORITHM_NAME = "linear_progress_interpolation"
ALGORITHM_VERSION = "wp06-smart-staging-1"
# Technical reconstruction tolerance — not a clinical tolerance.
TECHNICAL_NUMERICAL_TOLERANCE = 1e-9


class StagingTruthState(StrEnum):
    COMPUTED = "computed"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"
    # VERIFIED reserved for genuine external verification — never set by generation alone.
    VERIFIED = "verified"


class StagingFreshness(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class StagingReadinessState(StrEnum):
    AVAILABLE = "available"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class StagingReadiness:
    target_setup_available: StagingReadinessState
    target_version_valid: StagingReadinessState
    movement_data_available: StagingReadinessState
    constraints: StagingReadinessState
    validation: StagingReadinessState
    occlusion: StagingReadinessState
    clinical_axes: StagingReadinessState
    staging_proposal_available: StagingReadinessState
    doctor_review_required: bool
    notes: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "target_setup_available": self.target_setup_available.value,
            "target_version_valid": self.target_version_valid.value,
            "movement_data_available": self.movement_data_available.value,
            "constraints": self.constraints.value,
            "validation": self.validation.value,
            "occlusion": self.occlusion.value,
            "clinical_axes": self.clinical_axes.value,
            "staging_proposal_available": self.staging_proposal_available.value,
            "doctor_review_required": self.doctor_review_required,
            "notes": list(self.notes),
            "clinically_approved": False,
            "clinically_optimal": False,
        }


@dataclass(frozen=True)
class SmartStagingVersionMeta:
    staging_plan_id: str
    staging_version_id: str
    parent_staging_version_id: str | None
    case_id: str
    setup_plan_id: str
    source_setup_version_id: str
    created_at: str
    author_source: str
    description: str
    algorithm_name: str
    algorithm_version: str
    configuration: dict[str, Any]
    input_hash: str
    stage_count: int
    affected_tooth_count: int
    truth_state: StagingTruthState
    validation_status: str | None
    freshness: StagingFreshness
    limitations: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "staging_plan_id": self.staging_plan_id,
            "staging_version_id": self.staging_version_id,
            "parent_staging_version_id": self.parent_staging_version_id,
            "case_id": self.case_id,
            "setup_plan_id": self.setup_plan_id,
            "source_setup_version_id": self.source_setup_version_id,
            "created_at": self.created_at,
            "author_source": self.author_source,
            "description": self.description,
            "algorithm_name": self.algorithm_name,
            "algorithm_version": self.algorithm_version,
            "configuration": dict(self.configuration),
            "input_hash": self.input_hash,
            "stage_count": self.stage_count,
            "affected_tooth_count": self.affected_tooth_count,
            "truth_state": self.truth_state.value,
            "validation_status": self.validation_status,
            "freshness": self.freshness.value,
            "limitations": list(self.limitations),
            "immutable": True,
            "clinically_approved": False,
            "clinically_optimal": False,
        }


def stable_staging_plan_id(case_id: str) -> str:
    return f"staging:{case_id}"


__all__ = [
    "ALGORITHM_NAME",
    "ALGORITHM_VERSION",
    "TECHNICAL_NUMERICAL_TOLERANCE",
    "SmartStagingVersionMeta",
    "StagingFreshness",
    "StagingReadiness",
    "StagingReadinessState",
    "StagingTruthState",
    "stable_staging_plan_id",
]
