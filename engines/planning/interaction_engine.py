"""WP-04 Tooth Interaction Engine — commit adapter over existing P4 editing.

Does not reimplement staging or GeometricValidationEngine.
"""

from __future__ import annotations

from domain.movement.interaction import (
    ConstraintAvailability,
    CoordinateSpace,
    InteractionPhase,
    ToothInteractionState,
    ToothTransformState,
    can_transform,
    normalize_edit_reason,
    resolve_interaction_phase,
)
from domain.treatment_plan.setup import ToothMovement, TreatmentPlanProposal
from engines.planning.editing import TreatmentEditingApplication, TreatmentEditingError
from domain.treatment_plan.staging import StagingConfiguration
from engines.validation.geometric_engine import GeometricValidationConfiguration
from engines.validation.review_summary import assess_movement_constraints


def commit_tooth_transform(
    application: TreatmentEditingApplication,
    proposal: TreatmentPlanProposal,
    tooth_key: int | str,
    movement: ToothMovement,
    *,
    reason: str = "doctor_edit",
    staging_configuration: StagingConfiguration | None = None,
    validation_configuration: GeometricValidationConfiguration | None = None,
):
    """Commit a transform via P4 apply_edit_and_recalculate.

    Raises TreatmentEditingError for locked/excluded pose changes.
    """
    reason = normalize_edit_reason(reason)
    current = TreatmentEditingApplication._movement_for(proposal, tooth_key)
    if not can_transform(locked=current.locked, excluded=current.excluded):
        # Allow unlock / include (flag-only changes) through apply_edit's own checks.
        flag_only = current.pose_equal(movement) and (
            current.locked != movement.locked or current.excluded != movement.excluded
        )
        if not flag_only and reason != "doctor_reset" and reason != "reset":
            if current.locked and movement.locked:
                raise TreatmentEditingError(
                    f"Tooth {tooth_key} is locked; unlock before changing movement"
                )
            if current.excluded and movement.excluded:
                raise TreatmentEditingError(
                    f"Tooth {tooth_key} is excluded; include before changing movement"
                )

    staging_cfg = staging_configuration or StagingConfiguration(
        stage_count=2,
        mode="macro",
        movement_limits=None,
        engine_version="wp04-interaction",
    )
    validation_cfg = validation_configuration or GeometricValidationConfiguration(
        1.0, 0.001, 0.0
    )
    return application.apply_edit_and_recalculate(
        proposal,
        tooth_key,
        movement,
        staging_cfg,
        validation_cfg,
        reason=reason if reason != "reset" else "doctor_reset",
    )


def constraint_availability_for_proposal(
    proposal: TreatmentPlanProposal,
    staging_result,
) -> ConstraintAvailability:
    """Map existing validation honesty into the interaction constraint contract."""
    del proposal  # reserved for future per-tooth limit inspection
    status, _findings = assess_movement_constraints(staging_result)
    if status == "computed":
        return ConstraintAvailability.CONFIGURED
    if status == "unavailable":
        return ConstraintAvailability.UNAVAILABLE
    return ConstraintAvailability.NOT_CONFIGURED


def build_interaction_state(
    *,
    case_id: str,
    tooth_key: str,
    tooth_ref: str | None,
    arch: str | None,
    semantic_label: int | None,
    fdi_number: int | None,
    base: ToothMovement,
    current: ToothMovement,
    coordinate_space: CoordinateSpace = CoordinateSpace.WORLD,
    constraint_availability: ConstraintAvailability = ConstraintAvailability.UNAVAILABLE,
    version_id: str | None = None,
    transaction_id: str | None = None,
    updated_at: str | None = None,
    validation_status: str | None = None,
    source_mesh_sha256: str | None = None,
    transforming: bool = False,
    selected: bool = False,
    hovered: bool = False,
) -> ToothInteractionState:
    from domain.case.provenance import DataProvenance

    phase = resolve_interaction_phase(
        locked=current.locked,
        excluded=current.excluded,
        selected=selected,
        transforming=transforming,
        hovered=hovered,
        available=True,
    )
    notes: list[str] = []
    if coordinate_space is CoordinateSpace.WORLD:
        notes.append(
            "Transforms are geometric/world-space unless a validated clinical local frame exists."
        )
    if constraint_availability in (
        ConstraintAvailability.UNAVAILABLE,
        ConstraintAvailability.NOT_CONFIGURED,
    ):
        notes.append(
            "Movement constraints are not configured; geometric executability is not clinical validation."
        )
    notes.append("Interaction never implies doctor approval or clinical clearance.")
    return ToothInteractionState(
        case_id=case_id,
        tooth_ref=tooth_ref,
        tooth_key=tooth_key,
        semantic_label=semantic_label,
        fdi_number=fdi_number,
        arch=arch,
        source_mesh_sha256=source_mesh_sha256,
        base_transform=ToothTransformState.from_movement(base),
        current_transform=ToothTransformState.from_movement(current),
        coordinate_space=coordinate_space,
        locked=current.locked,
        excluded=current.excluded,
        phase=phase,
        constraint_availability=constraint_availability,
        provenance=DataProvenance.GENERATED,
        version_id=version_id,
        transaction_id=transaction_id,
        updated_at=updated_at,
        validation_status=validation_status,
        notes=tuple(notes),
    )


__all__ = [
    "ConstraintAvailability",
    "CoordinateSpace",
    "InteractionPhase",
    "ToothInteractionState",
    "ToothTransformState",
    "build_interaction_state",
    "can_transform",
    "commit_tooth_transform",
    "constraint_availability_for_proposal",
    "normalize_edit_reason",
    "resolve_interaction_phase",
]
