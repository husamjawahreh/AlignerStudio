"""Tooth movement / interaction domain contracts."""

from domain.movement.interaction import (
    EDIT_REASONS,
    ConstraintAvailability,
    CoordinateSpace,
    InteractionPhase,
    ToothInteractionState,
    ToothTransformState,
    can_transform,
    normalize_edit_reason,
    resolve_interaction_phase,
)

__all__ = [
    "EDIT_REASONS",
    "ConstraintAvailability",
    "CoordinateSpace",
    "InteractionPhase",
    "ToothInteractionState",
    "ToothTransformState",
    "can_transform",
    "normalize_edit_reason",
    "resolve_interaction_phase",
]
