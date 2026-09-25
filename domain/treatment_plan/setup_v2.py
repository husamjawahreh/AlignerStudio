"""Treatment Setup 2.0 contracts (WP-05).

Formalizes source / current / target separation, version lineage, readiness,
and comparison over existing P4 ``TreatmentPlanProposal`` — without inventing
clinical goals, FDI, axes, occlusion, or approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from domain.movement.interaction import (
    ConstraintAvailability,
    CoordinateSpace,
    ToothTransformState,
)
from domain.treatment_plan.setup import ToothMovement, TreatmentPlanProposal


class SetupLayer(StrEnum):
    """Named geometry/transform layers — never conflated."""

    SOURCE = "source"
    CURRENT = "current"
    TARGET = "target"


class ReadinessState(StrEnum):
    """Machine-readable capability signal — not an AI score."""

    AVAILABLE = "available"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ToothTargetState:
    """Per-tooth target planning state over immutable source geometry."""

    case_id: str
    tooth_ref: str | None
    tooth_key: str
    semantic_label: int | None
    fdi_number: int | None
    arch: str | None
    source_mesh_sha256: str | None
    source_transform: ToothTransformState
    current_transform: ToothTransformState
    target_transform: ToothTransformState
    coordinate_space: CoordinateSpace
    locked: bool
    excluded: bool
    constraint_availability: ConstraintAvailability
    validation_status: str | None
    limitations: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        delta = {
            key: self.target_transform.payload()[key] - self.current_transform.payload()[key]
            for key in self.target_transform.payload()
        }
        return {
            "case_id": self.case_id,
            "tooth_ref": self.tooth_ref,
            "tooth_key": self.tooth_key,
            "semantic_label": self.semantic_label,
            "fdi_number": self.fdi_number,
            "arch": self.arch,
            "source_mesh_sha256": self.source_mesh_sha256,
            "source_transform": self.source_transform.payload(),
            "current_transform": self.current_transform.payload(),
            "target_transform": self.target_transform.payload(),
            "delta_transform": delta,
            "coordinate_space": self.coordinate_space.value,
            "locked": self.locked,
            "excluded": self.excluded,
            "constraint_availability": self.constraint_availability.value,
            "validation_status": self.validation_status,
            "limitations": list(self.limitations),
            "clinically_approved": False,
            "changed": not self.current_transform.to_movement().pose_equal(
                self.target_transform.to_movement()
            ),
        }


@dataclass(frozen=True)
class TreatmentSetupReadiness:
    """Deterministic readiness gates — never collapse into an overall AI score."""

    real_geometry: ReadinessState
    identity: ReadinessState
    arch: ReadinessState
    transform: ReadinessState
    constraint: ReadinessState
    validation: ReadinessState
    occlusion: ReadinessState
    clinical_axes: ReadinessState
    notes: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "real_geometry": self.real_geometry.value,
            "identity": self.identity.value,
            "arch": self.arch.value,
            "transform": self.transform.value,
            "constraint": self.constraint.value,
            "validation": self.validation.value,
            "occlusion": self.occlusion.value,
            "clinical_axes": self.clinical_axes.value,
            "notes": list(self.notes),
            # Explicit: existence of target transforms never unlocks unsupported features.
            "unsupported_features_unlocked": False,
            "clinically_approved": False,
        }


@dataclass(frozen=True)
class TreatmentSetupVersionMeta:
    """Immutable version metadata (snapshot payload stored separately)."""

    version_id: str
    parent_version_id: str | None
    plan_id: str
    setup_plan_id: str
    created_at: str
    author_source: str
    description: str
    proposal_kind: str
    moved_tooth_count: int
    validation_status: str | None
    change_summary: str

    def payload(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "parent_version_id": self.parent_version_id,
            "plan_id": self.plan_id,
            "setup_plan_id": self.setup_plan_id,
            "created_at": self.created_at,
            "author_source": self.author_source,
            "description": self.description,
            "proposal_kind": self.proposal_kind,
            "moved_tooth_count": self.moved_tooth_count,
            "validation_status": self.validation_status,
            "change_summary": self.change_summary,
            "immutable": True,
            "clinically_approved": False,
        }


@dataclass(frozen=True)
class SetupToothDelta:
    tooth_key: str
    tooth_ref: str | None
    arch: str | None
    translation_delta: tuple[float, float, float]
    rotation_delta: tuple[float, float, float]
    changed: bool

    def payload(self) -> dict[str, Any]:
        return {
            "tooth_key": self.tooth_key,
            "tooth_ref": self.tooth_ref,
            "arch": self.arch,
            "translation_delta": list(self.translation_delta),
            "rotation_delta": list(self.rotation_delta),
            "changed": self.changed,
            # Geometric deltas only — not clinical intrusion/tip/torque claims.
            "terminology": "geometric",
        }


@dataclass(frozen=True)
class SetupComparisonResult:
    left_version_id: str
    right_version_id: str
    changed_teeth: tuple[SetupToothDelta, ...]
    unchanged_count: int
    left_validation_status: str | None
    right_validation_status: str | None
    notes: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "left_version_id": self.left_version_id,
            "right_version_id": self.right_version_id,
            "changed_teeth": [item.payload() for item in self.changed_teeth],
            "changed_count": len(self.changed_teeth),
            "unchanged_count": self.unchanged_count,
            "left_validation_status": self.left_validation_status,
            "right_validation_status": self.right_validation_status,
            "notes": list(self.notes),
            # Never rank or score plans.
            "clinical_ranking": None,
            "clinically_approved": False,
        }


def identity_transform() -> ToothTransformState:
    return ToothTransformState()


def movement_to_transform(movement: ToothMovement) -> ToothTransformState:
    return ToothTransformState.from_movement(movement)


def stable_setup_plan_id(case_id: str) -> str:
    """Stable lineage id for a case's Treatment Setup — not the content hash."""
    return f"setup:{case_id}"


def count_moved_teeth(proposal: TreatmentPlanProposal) -> int:
    if proposal.setup is None:
        return 0
    return sum(
        1
        for state in proposal.setup.target_states
        if not state.movement.pose_equal(ToothMovement())
    )


__all__ = [
    "ReadinessState",
    "SetupComparisonResult",
    "SetupLayer",
    "SetupToothDelta",
    "ToothTargetState",
    "TreatmentSetupReadiness",
    "TreatmentSetupVersionMeta",
    "count_moved_teeth",
    "identity_transform",
    "movement_to_transform",
    "stable_setup_plan_id",
]
