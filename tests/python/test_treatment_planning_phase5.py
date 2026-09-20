from dataclasses import replace

import pytest

from domain.tooth.identification import ArchType, IdentificationStatus
from domain.treatment_plan.setup import (
    ToothMovement,
    TreatmentObjective,
    TreatmentObjectiveType,
)
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.setup_engine import TreatmentPlanningEngine
from tests.fixtures.synthetic_arch import build_synthetic_arch
from tests.fixtures.synthetic_objectives import (
    mild_crowding_objective,
    rotation_objective,
    spacing_objective,
)


def identified_upper():
    return ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )


def test_deterministic_plan_generation_and_stable_hash() -> None:
    identification = identified_upper()
    objectives = (rotation_objective(), mild_crowding_objective(), spacing_objective())
    first = TreatmentPlanningEngine().generate("fixture-case", identification, objectives)
    second = TreatmentPlanningEngine().generate("fixture-case", identification, objectives)
    assert first == second
    assert first.plan_id == second.plan_id
    assert first.version_id == second.version_id
    assert first.setup is not None
    assert [state.tooth_number for state in first.setup.target_states] == [11, 12, 13]


def test_movement_transforms_in_tooth_coordinate_frame() -> None:
    identification = identified_upper()
    objective = TreatmentObjective(
        objective_id="frame-translation",
        objective_type=TreatmentObjectiveType.ALIGNMENT,
        description="Explicit local X translation.",
        movements=((11, ToothMovement(translation_x=1.0)),),
    )
    proposal = TreatmentPlanningEngine().generate("case", identification, (objective,))
    assert proposal.setup is not None
    state = proposal.setup.target_states[0]
    source = state.source_vertices[0]
    target = state.target_vertices[0]
    axis = state.coordinate_system.lateral_axis
    assert tuple(target[index] - source[index] for index in range(3)) == pytest.approx(axis)


def test_source_geometry_is_immutable_and_target_is_separate() -> None:
    identification = identified_upper()
    original = next(
        tooth.instance.mesh_vertices
        for tooth in identification.identified
        if tooth.identity.number == 11
    )
    objective = mild_crowding_objective()
    proposal = TreatmentPlanningEngine().generate("case", identification, (objective,))
    assert proposal.setup is not None
    target = proposal.setup.target_states[0]
    assert original == next(
        tooth.instance.mesh_vertices
        for tooth in identification.identified
        if tooth.identity.number == 11
    )
    assert target.source_vertices == original
    assert target.target_vertices != target.source_vertices


def test_missing_objectives_return_explicit_limitation() -> None:
    proposal = TreatmentPlanningEngine().generate("case", identified_upper(), ())
    assert proposal.setup is None
    assert proposal.limitations == ("No explicit treatment objectives were provided.",)
    assert proposal.clinical_approval is False


def test_objective_reference_to_unknown_tooth_is_limited() -> None:
    objective = TreatmentObjective(
        objective_id="unknown-tooth",
        objective_type=TreatmentObjectiveType.ALIGNMENT,
        description="Invalid engineering request.",
        movements=((99, ToothMovement(translation_x=1.0)),),
    )
    proposal = TreatmentPlanningEngine().generate("case", identified_upper(), (objective,))
    assert proposal.setup is None
    assert "unidentified teeth" in proposal.limitations[0]


def test_uncertain_identification_is_limited_without_fabrication() -> None:
    identification = identified_upper()
    uncertain = replace(
        identification,
        teeth=(
            replace(
                identification.teeth[0],
                identity=None,
                confidence=replace(
                    identification.teeth[0].confidence, status=IdentificationStatus.UNCERTAIN
                ),
            ),
            *identification.teeth[1:],
        ),
    )
    proposal = TreatmentPlanningEngine().generate("case", uncertain, (mild_crowding_objective(),))
    assert proposal.setup is None
    assert any("Uncertain" in limitation for limitation in proposal.limitations)


def test_fixture_provenance_is_preserved() -> None:
    proposal = TreatmentPlanningEngine().generate(
        "fixture-case", identified_upper(), (mild_crowding_objective(),)
    )
    assert proposal.fixture is True
    assert proposal.setup is not None
    assert proposal.setup.fixture is True
    assert proposal.setup.provenance.value == "generated"
    assert proposal.clinical_approval is False
    assert proposal.warnings
