from domain.case.provenance import DataProvenance
from domain.tooth.identification import (
    ArchType,
    IdentificationConfidence,
    IdentificationStatus,
    IdentifiedTooth,
    ToothCoordinateSystem,
    ToothIdentificationResult,
)
from domain.tooth.segmentation import ToothInstance
from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
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


def semantic_identification() -> ToothIdentificationResult:
    instance = ToothInstance(
        instance_id=0,
        triangle_indices=(0,),
        vertex_indices=(0, 1, 2),
        mesh_vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        mesh_faces=((0, 1, 2),),
        centroid=(1 / 3, 1 / 3, 0.0),
        confidence=0.0,
        provenance=DataProvenance.EXPERIMENTAL,
        fixture=True,
        tooth_ref="upper:instance:0",
        semantic_label=13,
        arch="upper",
    )
    frame = ToothCoordinateSystem(
        origin=instance.centroid,
        lateral_axis=(1.0, 0.0, 0.0),
        anterior_axis=(0.0, 1.0, 0.0),
        vertical_axis=(0.0, 0.0, 1.0),
        semantics=("engineering-reference-axis",) * 3,
    )
    return ToothIdentificationResult(
        arch=ArchType.UPPER,
        teeth=(
            IdentifiedTooth(
                instance=instance,
                identity=None,
                landmarks=None,
                coordinate_system=frame,
                confidence=IdentificationConfidence(
                    0.0, IdentificationStatus.UNCERTAIN, ("semantic-only",)
                ),
                provenance=DataProvenance.EXPERIMENTAL,
                fixture=True,
                tooth_ref=instance.tooth_ref,
                semantic_label=instance.semantic_label,
                planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL.value,
            ),
        ),
        provenance=DataProvenance.EXPERIMENTAL,
        fixture=True,
        notes="validated_real_case; correspondence_verified=true",
    )


def test_semantic_only_input_plans_without_fdi_and_preserves_ref() -> None:
    identification = semantic_identification()
    treatment_input = TreatmentPlanningInput.from_identification(
        identification, planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL
    )
    objective = TreatmentObjective(
        "semantic-review",
        TreatmentObjectiveType.ALIGNMENT,
        "Non-clinical experimental demonstration objective.",
        (("upper:instance:0", ToothMovement(translation_x=0.1)),),
    )
    proposal = TreatmentPlanningEngine().generate_from_input(
        "semantic-only", treatment_input, (objective,)
    )
    assert proposal.setup is not None
    assert proposal.planning_mode == "semantic_only_experimental"
    state = proposal.setup.target_states[0]
    assert state.tooth_ref == "upper:instance:0"
    assert state.tooth_number is None
    assert state.semantic_label == 13


def test_semantic_only_unknown_ref_fails_closed() -> None:
    treatment_input = TreatmentPlanningInput.from_identification(
        semantic_identification(), planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL
    )
    objective = TreatmentObjective(
        "unknown-semantic-review",
        TreatmentObjectiveType.ALIGNMENT,
        "Non-clinical experimental demonstration objective.",
        (("upper:instance:99", ToothMovement()),),
    )
    proposal = TreatmentPlanningEngine().generate_from_input(
        "semantic-only-unknown", treatment_input, (objective,)
    )
    assert proposal.setup is None
    assert "unknown tooth references" in proposal.limitations[0]
