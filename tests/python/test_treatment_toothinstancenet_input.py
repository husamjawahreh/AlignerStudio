from domain.case.provenance import DataProvenance
from domain.tooth.identification import ArchType, ToothIdentificationResult
from domain.treatment_plan.input import TreatmentPlanningInput
from domain.treatment_plan.setup import ToothMovement, TreatmentObjective, TreatmentObjectiveType
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.setup_engine import TreatmentPlanningEngine
from services.api.app.treatment_sessions import TreatmentSessionStore
from tests.fixtures.synthetic_arch import build_synthetic_arch


def objectives():
    return (
        TreatmentObjective(
            "development-alignment",
            TreatmentObjectiveType.ALIGNMENT,
            "Explicit development review movement; not a clinical recommendation.",
            ((11, ToothMovement(translation_x=0.1)),),
            assumptions=("Development/demo objective only.",),
        ),
    )


def test_domain_input_reaches_existing_planner_and_stager() -> None:
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    treatment_input = TreatmentPlanningInput.from_identification(identification)
    session = TreatmentSessionStore().create_from_treatment_input(
        "toothinstancenet-development", treatment_input, objectives()
    )
    assert session.proposal.setup is not None
    assert session.staging.stage_count == 3
    assert session.proposal.fixture is True
    assert session.proposal.provenance is DataProvenance.GENERATED


def test_incomplete_review_input_stops_before_setup() -> None:
    identification = ToothIdentificationResult(
        arch=ArchType.UPPER,
        teeth=(),
        provenance=DataProvenance.EXPERIMENTAL,
        fixture=True,
        notes="Explicit incomplete fixture diagnostic.",
    )
    treatment_input = TreatmentPlanningInput.from_identification(
        identification, diagnostics=("missing FDI diagnostics",)
    )
    proposal = TreatmentPlanningEngine().generate_from_input(
        "incomplete-development", treatment_input, objectives()
    )
    assert proposal.setup is None
    assert proposal.limitations == ("missing FDI diagnostics",)
    assert proposal.fixture is True
    assert proposal.provenance is DataProvenance.EXPERIMENTAL
