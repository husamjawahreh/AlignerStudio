from domain.tooth.identification import ArchType
from domain.treatment_plan.setup import ToothMovement, TreatmentObjective, TreatmentObjectiveType
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.setup_engine import TreatmentPlanningEngine
from tests.fixtures.synthetic_arch import build_synthetic_arch


def test_deterministic_planner_covers_all_identified_teeth_without_inventing_movement() -> None:
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    proposal = TreatmentPlanningEngine().generate(
        "p3-case",
        identification,
        (
            TreatmentObjective(
                objective_id="explicit-review-objective",
                objective_type=TreatmentObjectiveType.ALIGNMENT,
                description="Explicit review movement.",
                movements=((11, ToothMovement(translation_x=0.5)),),
            ),
        ),
    )

    assert proposal.setup is not None
    assert len(proposal.setup.target_states) == len(identification.identified)
    moved = {state.tooth_number: state.movement for state in proposal.setup.target_states}
    assert moved[11] == ToothMovement(translation_x=0.5)
    assert all(
        movement == ToothMovement()
        for tooth_number, movement in moved.items()
        if tooth_number != 11
    )
    assert any(
        state.target_vertices != state.source_vertices
        for state in proposal.setup.target_states
        if state.tooth_number == 11
    )
