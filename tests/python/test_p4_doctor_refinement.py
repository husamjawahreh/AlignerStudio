"""P4 doctor refinement — edit → restage → validate with lock/exclude/angulation."""

from __future__ import annotations

import pytest

from domain.treatment_plan.setup import ProposalKind, ToothMovement
from domain.treatment_plan.staging import StagingConfiguration
from engines.planning.editing import TreatmentEditingApplication, TreatmentEditingError
from engines.planning.staging_engine import resolve_dynamic_stage_count
from engines.validation.geometric_engine import GeometricValidationConfiguration
from tests.python.test_doctor_editing_phase9 import build_proposal, validation_config


def test_apply_edit_and_recalculate_refreshes_stages_and_validation() -> None:
    application = TreatmentEditingApplication()
    original = build_proposal()
    result = application.apply_edit_and_recalculate(
        original,
        11,
        ToothMovement(translation_x=0.55, angulation=2.0),
        StagingConfiguration(stage_count=3, mode="macro"),
        validation_config(),
        timestamp="2026-09-25T00:00:00Z",
    )
    assert result.proposal.proposal_kind is ProposalKind.RECALCULATED
    assert result.proposal.edit_history[-1].new_movement.angulation == 2.0
    assert result.staging.stage_count >= 3
    assert result.validation.stage_results
    final = result.staging.final_stage
    target = next(state for state in result.proposal.setup.target_states if state.tooth_number == 11)
    staged = next(state for state in final.tooth_states if state.tooth_number == 11)
    assert staged.vertices == target.target_vertices


def test_locked_tooth_rejects_pose_edits_but_allows_unlock() -> None:
    application = TreatmentEditingApplication()
    original = build_proposal()
    locked = application.apply_edit(
        original, 11, ToothMovement(translation_x=0.2, locked=True), timestamp="1"
    )
    with pytest.raises(TreatmentEditingError, match="locked"):
        application.apply_edit(
            locked, 11, ToothMovement(translation_x=0.9, locked=True), timestamp="2"
        )
    unlocked = application.apply_edit(
        locked, 11, ToothMovement(translation_x=0.2, locked=False), timestamp="3"
    )
    assert unlocked.setup.target_states[0].movement.locked is False


def test_excluded_tooth_keeps_source_geometry() -> None:
    application = TreatmentEditingApplication()
    original = build_proposal()
    source = next(state for state in original.setup.source_states if state.tooth_number == 11)
    excluded = application.apply_edit(
        original,
        11,
        ToothMovement(translation_x=1.5, rotation=8.0, excluded=True),
        timestamp="1",
    )
    target = next(state for state in excluded.setup.target_states if state.tooth_number == 11)
    assert target.movement.excluded is True
    assert target.target_vertices == source.source_vertices


def test_dynamic_stage_count_grows_with_movement_magnitude() -> None:
    proposal = build_proposal()
    edited = TreatmentEditingApplication().apply_edit(
        proposal,
        11,
        ToothMovement(translation_x=3.0, translation_y=2.0, rotation=20.0),
        timestamp="1",
    )
    macro = resolve_dynamic_stage_count(edited, base_count=3, mode="macro")
    micro = resolve_dynamic_stage_count(edited, base_count=3, mode="micro")
    assert macro >= 3
    assert micro >= macro


def test_angulation_affects_lateral_rotation_transform() -> None:
    application = TreatmentEditingApplication()
    original = build_proposal()
    tipped = application.apply_edit(original, 11, ToothMovement(tip=4.0), timestamp="1")
    angled = application.apply_edit(original, 11, ToothMovement(angulation=4.0), timestamp="2")
    tip_target = next(state for state in tipped.setup.target_states if state.tooth_number == 11)
    ang_target = next(state for state in angled.setup.target_states if state.tooth_number == 11)
    assert tip_target.target_vertices == ang_target.target_vertices
    assert tip_target.target_vertices != next(
        state for state in original.setup.target_states if state.tooth_number == 11
    ).target_vertices
