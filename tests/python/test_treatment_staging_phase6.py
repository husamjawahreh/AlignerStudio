from dataclasses import replace

import pytest

from domain.tooth.identification import ArchType
from domain.treatment_plan.setup import (
    ToothMovement,
    TreatmentObjective,
    TreatmentObjectiveType,
)
from domain.treatment_plan.staging import StagingConfiguration
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.staging_engine import TreatmentStagingEngine
from tests.fixtures.synthetic_arch import build_synthetic_arch


def build_proposal(objectives=None):
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    if objectives is None:
        objectives = (
            TreatmentObjective(
                objective_id="fixture-combined",
                objective_type=TreatmentObjectiveType.ROTATION_CORRECTION,
                description="Synthetic combined movement.",
                movements=(
                    (11, ToothMovement(translation_x=1.0, rotation=10.0, tip=2.0)),
                    (12, ToothMovement(translation_y=0.5, torque=-4.0)),
                ),
            ),
            TreatmentObjective(
                objective_id="fixture-zero",
                objective_type=TreatmentObjectiveType.ALIGNMENT,
                description="Synthetic zero movement tooth.",
                movements=((13, ToothMovement()),),
            ),
        )
    return TreatmentPlanningEngine().generate("fixture-case", identification, objectives)


def test_stage_count_and_deterministic_ordering() -> None:
    result = TreatmentStagingEngine().generate(
        build_proposal(), StagingConfiguration(stage_count=4)
    )
    assert result.limitations == ()
    assert result.stage_count == 4
    assert [stage.stage_index for stage in result.stages] == [0, 1, 2, 3]
    assert all(
        [state.tooth_number for state in stage.tooth_states] == [11, 12, 13]
        for stage in result.stages
    )


def test_stage_zero_is_original_and_immutable() -> None:
    proposal = build_proposal()
    original = proposal.setup.source_states[0].source_vertices
    result = TreatmentStagingEngine().generate(proposal, StagingConfiguration(stage_count=3))
    stage_zero = result.stages[0].tooth_states[0]
    assert stage_zero.vertices == original
    assert stage_zero.movement.progress == 0.0
    assert stage_zero.movement.movement == ToothMovement()
    assert proposal.setup.source_states[0].source_vertices == original


def test_intermediate_movements_are_linear() -> None:
    result = TreatmentStagingEngine().generate(
        build_proposal(), StagingConfiguration(stage_count=3)
    )
    state = result.stages[1].tooth_states[0]
    assert state.movement.progress == pytest.approx(0.5)
    assert state.movement.movement == ToothMovement(translation_x=0.5, rotation=5.0, tip=1.0)
    source = state.source_vertices[0]
    final = state.final_target_vertices[0]
    assert state.vertices[0] == pytest.approx(
        tuple((before + after) / 2 for before, after in zip(source, final, strict=True))
    )


def test_final_stage_exactly_matches_phase5_target() -> None:
    proposal = build_proposal()
    result = TreatmentStagingEngine().generate(proposal, StagingConfiguration(stage_count=5))
    final_states = {state.tooth_number: state for state in result.final_stage.tooth_states}
    target_states = {state.tooth_number: state for state in proposal.setup.target_states}
    for tooth_number in target_states:
        assert final_states[tooth_number].vertices == target_states[tooth_number].target_vertices
        assert final_states[tooth_number].movement.movement == target_states[tooth_number].movement
        assert (
            final_states[tooth_number].coordinate_system
            == target_states[tooth_number].coordinate_system
        )


def test_coordinate_system_and_source_relationship_are_preserved() -> None:
    proposal = build_proposal()
    result = TreatmentStagingEngine().generate(proposal, StagingConfiguration(stage_count=3))
    for stage in result.stages:
        for state in stage.tooth_states:
            target = next(
                item
                for item in proposal.setup.target_states
                if item.tooth_number == state.tooth_number
            )
            assert state.coordinate_system == target.coordinate_system
            assert state.source_instance_id == target.source_instance_id
            assert state.final_target_vertices == target.target_vertices
            assert state.provenance == target.provenance


def test_zero_movement_tooth_remains_constant() -> None:
    result = TreatmentStagingEngine().generate(
        build_proposal(), StagingConfiguration(stage_count=4)
    )
    states = [stage.tooth_states[2] for stage in result.stages]
    assert all(state.vertices == states[0].vertices for state in states)
    assert all(state.movement.movement == ToothMovement() for state in states)


def test_stage_and_staging_hashes_are_stable() -> None:
    proposal = build_proposal()
    configuration = StagingConfiguration(stage_count=4)
    first = TreatmentStagingEngine().generate(proposal, configuration)
    second = TreatmentStagingEngine().generate(proposal, configuration)
    assert first == second
    assert first.staging_id == second.staging_id
    assert [stage.stage_id for stage in first.stages] == [stage.stage_id for stage in second.stages]
    assert [stage.stage_hash for stage in first.stages] == [
        stage.stage_hash for stage in second.stages
    ]


def test_provenance_and_fixture_labeling_are_preserved() -> None:
    result = TreatmentStagingEngine().generate(
        build_proposal(), StagingConfiguration(stage_count=2)
    )
    assert result.provenance.value == "generated"
    assert result.fixture is True
    assert all(stage.fixture for stage in result.stages)
    assert all(state.fixture for stage in result.stages for state in stage.tooth_states)
    assert result.warnings


def test_missing_setup_returns_explicit_limitation() -> None:
    proposal = build_proposal(())
    result = TreatmentStagingEngine().generate(proposal, StagingConfiguration(stage_count=2))
    assert result.stages == ()
    assert "no setup" in result.limitations[0].lower()


def test_invalid_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="stage_count"):
        StagingConfiguration(stage_count=1)


def test_mismatched_source_target_geometry_is_rejected() -> None:
    proposal = build_proposal()
    source = proposal.setup.source_states[0]
    malformed = replace(source, source_vertices=source.source_vertices[:-1])
    malformed_setup = replace(
        proposal.setup, source_states=(malformed, *proposal.setup.source_states[1:])
    )
    malformed_proposal = replace(proposal, setup=malformed_setup)
    with pytest.raises(ValueError, match="vertex counts differ"):
        TreatmentStagingEngine().generate(malformed_proposal, StagingConfiguration(stage_count=2))
