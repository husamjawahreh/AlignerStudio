"""Deterministic Phase 5 objective fixtures; not clinical prescriptions."""

from domain.treatment_plan.setup import (
    ToothMovement,
    TreatmentObjective,
    TreatmentObjectiveType,
)


def mild_crowding_objective() -> TreatmentObjective:
    return TreatmentObjective(
        objective_id="fixture-alignment-11",
        objective_type=TreatmentObjectiveType.ALIGNMENT,
        description="Engineering fixture alignment movement for tooth 11.",
        movements=((11, ToothMovement(translation_x=0.2)),),
        assumptions=("Synthetic mild crowding fixture only.",),
    )


def spacing_objective() -> TreatmentObjective:
    return TreatmentObjective(
        objective_id="fixture-spacing-12",
        objective_type=TreatmentObjectiveType.SPACING,
        description="Engineering fixture spacing movement for tooth 12.",
        movements=((12, ToothMovement(translation_y=0.15)),),
        assumptions=("Synthetic spacing fixture only.",),
    )


def rotation_objective() -> TreatmentObjective:
    return TreatmentObjective(
        objective_id="fixture-rotation-13",
        objective_type=TreatmentObjectiveType.ROTATION_CORRECTION,
        description="Engineering fixture rotation movement for tooth 13.",
        movements=((13, ToothMovement(rotation=5.0, tip=1.0, torque=-1.0)),),
        assumptions=("Synthetic rotation fixture only.",),
    )
