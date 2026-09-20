from dataclasses import replace

import pytest

from domain.tooth.identification import ArchType
from domain.treatment_plan.setup import ProposalKind, ToothMovement
from domain.treatment_plan.staging import StagingConfiguration
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.editing import TreatmentEditingApplication, TreatmentEditingError
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.validation.geometric_engine import GeometricValidationConfiguration
from tests.fixtures.synthetic_arch import build_synthetic_arch
from tests.fixtures.synthetic_objectives import mild_crowding_objective, spacing_objective


def build_proposal():
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    return TreatmentPlanningEngine().generate(
        "fixture-edit-case",
        identification,
        (mild_crowding_objective(), spacing_objective()),
    )


def validation_config() -> GeometricValidationConfiguration:
    return GeometricValidationConfiguration(0.25, 0.001, 0.0)


def test_edit_one_tooth_creates_explicit_history_and_new_hash() -> None:
    original = build_proposal()
    edited = TreatmentEditingApplication().apply_edit(
        original,
        11,
        ToothMovement(translation_x=0.7, rotation=3.0),
        timestamp="2026-09-19T00:00:00Z",
    )
    assert edited.plan_id != original.plan_id
    assert edited.version_id != original.version_id
    assert edited.proposal_kind is ProposalKind.DOCTOR_EDITED
    assert len(edited.edit_history) == 1
    edit = edited.edit_history[0]
    assert edit.tooth_number == 11
    assert edit.reason == "doctor_edit"
    assert edit.timestamp == "2026-09-19T00:00:00Z"
    assert edit.previous_movement == original.setup.target_states[0].movement
    assert edited.setup.target_states[0].movement == ToothMovement(translation_x=0.7, rotation=3.0)


def test_multiple_edits_preserve_unchanged_tooth_and_source_geometry() -> None:
    original = build_proposal()
    original_sources = {
        state.tooth_number: state.source_vertices for state in original.setup.source_states
    }
    application = TreatmentEditingApplication()
    edited = application.apply_edit(original, 11, ToothMovement(translation_x=0.5), timestamp="1")
    edited = application.apply_edit(edited, 12, ToothMovement(translation_y=0.4), timestamp="2")
    target_by_tooth = {state.tooth_number: state for state in edited.setup.target_states}
    original_by_tooth = {state.tooth_number: state for state in original.setup.target_states}
    assert len(edited.edit_history) == 2
    assert target_by_tooth[12].movement == ToothMovement(translation_y=0.4)
    assert target_by_tooth[11].movement == ToothMovement(translation_x=0.5)
    assert target_by_tooth[11].source_vertices == original_sources[11]
    assert target_by_tooth[12].source_vertices == original_sources[12]
    assert target_by_tooth[11].source_faces == original_by_tooth[11].source_faces


def test_cancel_returns_original_proposal_and_reset_tooth_restores_initial_movement() -> None:
    original = build_proposal()
    application = TreatmentEditingApplication()
    edited = application.apply_edit(original, 11, ToothMovement(translation_x=1.0), timestamp="1")
    assert application.cancel(original) == original
    reset = application.reset_tooth(edited, 11, timestamp="2")
    assert reset.setup.target_states[0].movement == original.setup.target_states[0].movement
    assert reset.edit_history[-1].reason == "doctor_reset"


def test_reset_all_restores_all_original_movements() -> None:
    original = build_proposal()
    application = TreatmentEditingApplication()
    edited = application.apply_edit(original, 11, ToothMovement(translation_x=1.0), timestamp="1")
    edited = application.apply_edit(edited, 12, ToothMovement(translation_y=1.0), timestamp="2")
    reset = application.reset_all(edited, timestamp="3")
    original_movements = {
        state.tooth_number: state.movement for state in original.setup.target_states
    }
    reset_movements = {state.tooth_number: state.movement for state in reset.setup.target_states}
    assert reset_movements == original_movements


def test_recalculate_is_deterministic_and_regenerates_stages_and_validation() -> None:
    application = TreatmentEditingApplication()
    edited = application.apply_edit(
        build_proposal(), 11, ToothMovement(translation_x=0.3), timestamp="fixed"
    )
    first = application.recalculate(
        edited, StagingConfiguration(stage_count=3), validation_config()
    )
    second = application.recalculate(
        edited, StagingConfiguration(stage_count=3), validation_config()
    )
    assert first == second
    assert first.proposal.proposal_kind is ProposalKind.RECALCULATED
    assert first.proposal.plan_id != edited.plan_id
    assert first.staging.stage_count == 3
    assert first.validation.stage_results
    final = first.staging.final_stage
    target_by_tooth = {state.tooth_number: state for state in first.proposal.setup.target_states}
    for state in final.tooth_states:
        assert state.vertices == target_by_tooth[state.tooth_number].target_vertices
    assert first.recalculation_id == second.recalculation_id


def test_recalculation_preserves_edit_history_and_source_geometry() -> None:
    original = build_proposal()
    application = TreatmentEditingApplication()
    edited = application.apply_edit(original, 11, ToothMovement(rotation=4.0), timestamp="fixed")
    recalculated = application.recalculate(
        edited, StagingConfiguration(stage_count=2), validation_config()
    )
    assert recalculated.proposal.edit_history == edited.edit_history
    assert recalculated.proposal.setup.source_states == original.setup.source_states


def test_invalid_or_missing_edit_is_rejected() -> None:
    application = TreatmentEditingApplication()
    with pytest.raises(TreatmentEditingError, match="finite"):
        application.apply_edit(build_proposal(), 11, ToothMovement(translation_x=float("nan")))
    with pytest.raises(TreatmentEditingError, match="not editable"):
        application.apply_edit(build_proposal(), 99, ToothMovement(translation_x=1.0))
    missing = replace(build_proposal(), setup=None)
    with pytest.raises(TreatmentEditingError, match="no editable setup"):
        application.apply_edit(missing, 11, ToothMovement(translation_x=1.0))


def test_fixture_behavior_and_provenance_are_preserved() -> None:
    application = TreatmentEditingApplication()
    edited = application.apply_edit(
        build_proposal(), 11, ToothMovement(translation_x=0.2), timestamp="fixture"
    )
    recalculated = application.recalculate(
        edited, StagingConfiguration(stage_count=2), validation_config()
    )
    assert recalculated.proposal.fixture is True
    assert recalculated.staging.fixture is True
    assert recalculated.validation.fixture is True
    assert recalculated.proposal.provenance.value == "generated"
