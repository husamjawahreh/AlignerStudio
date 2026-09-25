"""Tooth Interaction Engine domain contracts (WP-04).

Thin formalization over existing ``ToothMovement`` / ``DoctorMovementEdit``.
Does not invent clinical axes, FDI, or movement limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from domain.case.provenance import DataProvenance
from domain.treatment_plan.setup import ToothMovement

# Allowed edit provenance labels — never invent AI authorship.
EDIT_REASONS = frozenset(
    {
        "doctor_edit",
        "doctor_reset",
        "gizmo_edit",
        "numeric_edit",
        "reset",
        "system_restore",
    }
)


class InteractionPhase(StrEnum):
    """UI/interaction phase — separate from clinical truth state."""

    IDLE = "idle"
    HOVERED = "hovered"
    SELECTED = "selected"
    ACTIVELY_TRANSFORMING = "actively_transforming"
    LOCKED = "locked"
    EXCLUDED = "excluded"
    REVIEW_REQUIRED = "review_required"
    UNAVAILABLE = "unavailable"


class ConstraintAvailability(StrEnum):
    """Honest constraint contract — never invent thresholds."""

    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"
    VIOLATING = "violating"
    UNAVAILABLE = "unavailable"


class CoordinateSpace(StrEnum):
    """Transform frame. Clinical local axes only when genuinely available."""

    WORLD = "world"
    ENGINEERING_LOCAL = "engineering_local"
    CLINICAL_LOCAL = "clinical_local"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ToothTransformState:
    """6-DOF transform snapshot — maps 1:1 onto ToothMovement pose DOFs."""

    translation_x: float = 0.0
    translation_y: float = 0.0
    translation_z: float = 0.0
    rotation: float = 0.0
    tip: float = 0.0
    torque: float = 0.0
    angulation: float = 0.0
    intrusion: float = 0.0
    extrusion: float = 0.0

    def to_movement(self, *, locked: bool = False, excluded: bool = False) -> ToothMovement:
        return ToothMovement(
            translation_x=self.translation_x,
            translation_y=self.translation_y,
            translation_z=self.translation_z,
            rotation=self.rotation,
            tip=self.tip,
            torque=self.torque,
            angulation=self.angulation,
            intrusion=self.intrusion,
            extrusion=self.extrusion,
            locked=locked,
            excluded=excluded,
        )

    @classmethod
    def from_movement(cls, movement: ToothMovement) -> ToothTransformState:
        return cls(
            translation_x=movement.translation_x,
            translation_y=movement.translation_y,
            translation_z=movement.translation_z,
            rotation=movement.rotation,
            tip=movement.tip,
            torque=movement.torque,
            angulation=movement.angulation,
            intrusion=movement.intrusion,
            extrusion=movement.extrusion,
        )

    def payload(self) -> dict[str, float]:
        return {
            "translation_x": self.translation_x,
            "translation_y": self.translation_y,
            "translation_z": self.translation_z,
            "rotation": self.rotation,
            "tip": self.tip,
            "torque": self.torque,
            "angulation": self.angulation,
            "intrusion": self.intrusion,
            "extrusion": self.extrusion,
        }


@dataclass(frozen=True)
class ToothInteractionState:
    """Persistent interaction state for one semantic tooth instance."""

    case_id: str
    tooth_ref: str | None
    tooth_key: str
    semantic_label: int | None
    fdi_number: int | None
    arch: str | None
    source_mesh_sha256: str | None
    base_transform: ToothTransformState
    current_transform: ToothTransformState
    coordinate_space: CoordinateSpace
    locked: bool
    excluded: bool
    phase: InteractionPhase
    constraint_availability: ConstraintAvailability
    provenance: DataProvenance
    version_id: str | None
    transaction_id: str | None
    updated_at: str | None
    validation_status: str | None
    notes: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "tooth_ref": self.tooth_ref,
            "tooth_key": self.tooth_key,
            "semantic_label": self.semantic_label,
            "fdi_number": self.fdi_number,
            "arch": self.arch,
            "source_mesh_sha256": self.source_mesh_sha256,
            "base_transform": self.base_transform.payload(),
            "current_transform": self.current_transform.payload(),
            "delta_transform": _delta(self.base_transform, self.current_transform),
            "coordinate_space": self.coordinate_space.value,
            "locked": self.locked,
            "excluded": self.excluded,
            "phase": self.phase.value,
            "constraint_availability": self.constraint_availability.value,
            "provenance": self.provenance.value,
            "version_id": self.version_id,
            "transaction_id": self.transaction_id,
            "updated_at": self.updated_at,
            "validation_status": self.validation_status,
            "notes": list(self.notes),
            # Explicit: geometric executability ≠ clinical approval.
            "clinically_approved": False,
        }


def normalize_edit_reason(reason: str | None) -> str:
    if reason in EDIT_REASONS:
        return reason  # type: ignore[return-value]
    return "doctor_edit"


def resolve_interaction_phase(
    *,
    locked: bool,
    excluded: bool,
    selected: bool,
    transforming: bool,
    hovered: bool,
    available: bool,
) -> InteractionPhase:
    if not available:
        return InteractionPhase.UNAVAILABLE
    if locked:
        return InteractionPhase.LOCKED
    if excluded:
        return InteractionPhase.EXCLUDED
    if transforming:
        return InteractionPhase.ACTIVELY_TRANSFORMING
    if selected:
        return InteractionPhase.SELECTED
    if hovered:
        return InteractionPhase.HOVERED
    return InteractionPhase.IDLE


def can_transform(*, locked: bool, excluded: bool, available: bool = True) -> bool:
    """Geometric manipulability gate — not clinical permission."""
    return available and not locked and not excluded


def _delta(base: ToothTransformState, current: ToothTransformState) -> dict[str, float]:
    return {
        "translation_x": current.translation_x - base.translation_x,
        "translation_y": current.translation_y - base.translation_y,
        "translation_z": current.translation_z - base.translation_z,
        "rotation": current.rotation - base.rotation,
        "tip": current.tip - base.tip,
        "torque": current.torque - base.torque,
        "angulation": current.angulation - base.angulation,
        "intrusion": current.intrusion - base.intrusion,
        "extrusion": current.extrusion - base.extrusion,
    }
