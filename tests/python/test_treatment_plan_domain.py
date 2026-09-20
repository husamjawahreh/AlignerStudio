from domain.case.provenance import DataProvenance
from domain.tooth.models import Tooth
from domain.treatment_plan.models import Stage, ToothPosition, TreatmentPlan


def test_treatment_plan_stage_count() -> None:
    stage = Stage(
        index=0,
        tooth_positions=(ToothPosition(tooth=Tooth(fdi_number=11)),),
        provenance=DataProvenance.GENERATED,
        fixture=True,
        notes="fixture",
    )
    plan = TreatmentPlan(
        case_id="c1", stages=(stage,), provenance=DataProvenance.GENERATED, fixture=True
    )
    assert plan.stage_count == 1
    assert plan.stages[0].fixture is True
