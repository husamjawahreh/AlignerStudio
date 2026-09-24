"""Phase 5 treatment setup domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ToothCoordinateSystem

Vector3 = tuple[float, float, float]


class TreatmentObjectiveType(str, Enum):
    ALIGNMENT = "alignment"
    SPACING = "spacing"
    ROTATION_CORRECTION = "rotation_correction"
    ARCH_COORDINATION = "arch_coordination"


class ProposalKind(str, Enum):
    ORIGINAL_GENERATED = "original_generated"
    DOCTOR_EDITED = "doctor_edited"
    RECALCULATED = "recalculated"


@dataclass(frozen=True)
class ToothMovement:
    """Explicit movement request expressed in the tooth local frame."""

    translation_x: float = 0.0
    translation_y: float = 0.0
    translation_z: float = 0.0
    rotation: float = 0.0
    tip: float = 0.0
    torque: float = 0.0
    angulation: float = 0.0
    intrusion: float = 0.0
    extrusion: float = 0.0
    locked: bool = False
    excluded: bool = False

    @property
    def translation(self) -> Vector3:
        return (self.translation_x, self.translation_y, self.translation_z)

    @property
    def vertical_translation(self) -> float:
        return self.translation_z + self.extrusion - self.intrusion

    @property
    def lateral_rotation_degrees(self) -> float:
        """Tip + angulation share the tooth lateral axis (mesiodistal tipping)."""
        return self.tip + self.angulation

    def plus(self, other: ToothMovement) -> ToothMovement:
        return ToothMovement(
            translation_x=self.translation_x + other.translation_x,
            translation_y=self.translation_y + other.translation_y,
            translation_z=self.translation_z + other.translation_z,
            rotation=self.rotation + other.rotation,
            tip=self.tip + other.tip,
            torque=self.torque + other.torque,
            angulation=self.angulation + other.angulation,
            intrusion=self.intrusion + other.intrusion,
            extrusion=self.extrusion + other.extrusion,
            locked=self.locked or other.locked,
            excluded=self.excluded or other.excluded,
        )

    def pose_equal(self, other: ToothMovement) -> bool:
        """Compare pose DOFs only (ignore lock/exclude flags)."""
        return (
            self.translation_x == other.translation_x
            and self.translation_y == other.translation_y
            and self.translation_z == other.translation_z
            and self.rotation == other.rotation
            and self.tip == other.tip
            and self.torque == other.torque
            and self.angulation == other.angulation
            and self.intrusion == other.intrusion
            and self.extrusion == other.extrusion
        )


@dataclass(frozen=True)
class DoctorMovementEdit:
    """One explicit doctor change to one tooth movement."""

    edit_id: str
    tooth_number: int | str
    previous_movement: ToothMovement
    new_movement: ToothMovement
    timestamp: str
    version_id: str
    provenance: DataProvenance
    reason: str = "doctor_edit"


@dataclass(frozen=True)
class TreatmentObjective:
    """An explicit objective with explicit per-tooth movements."""

    objective_id: str
    objective_type: TreatmentObjectiveType
    description: str
    movements: tuple[tuple[int | str, ToothMovement], ...]
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.objective_id.strip():
            raise ValueError("Treatment objective requires a stable objective_id")
        tooth_refs = [ref for ref, _ in self.movements]
        if len(tooth_refs) != len(set(tooth_refs)):
            raise ValueError("Objective movements must have unique tooth references")


@dataclass(frozen=True)
class TargetToothState:
    """A proposed transformed state; source geometry remains unchanged."""

    tooth_number: int | None
    source_instance_id: int
    source_vertices: tuple[Vector3, ...]
    source_faces: tuple[tuple[int, int, int], ...]
    target_vertices: tuple[Vector3, ...]
    target_faces: tuple[tuple[int, int, int], ...]
    coordinate_system: ToothCoordinateSystem
    movement: ToothMovement
    provenance: DataProvenance
    fixture: bool
    notes: str = ""
    tooth_ref: str | None = None
    semantic_label: int | None = None
    arch: str | None = None
    planning_mode: str = "clinical_fdi"


@dataclass(frozen=True)
class TreatmentSetup:
    """Immutable source/target scene representation for one setup."""

    source_states: tuple[TargetToothState, ...]
    target_states: tuple[TargetToothState, ...]
    provenance: DataProvenance
    fixture: bool
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TreatmentPlanProposal:
    """Deterministic, reviewable setup proposal; not a clinical approval."""

    plan_id: str
    version_id: str
    case_id: str
    objectives: tuple[TreatmentObjective, ...]
    setup: TreatmentSetup | None
    provenance: DataProvenance
    fixture: bool
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    clinical_approval: bool = False
    proposal_kind: ProposalKind = ProposalKind.ORIGINAL_GENERATED
    edit_history: tuple[DoctorMovementEdit, ...] = ()
    planning_mode: str = "clinical_fdi"
