from domain.case.provenance import DataProvenance
from engines.planning.placeholder import PlaceholderPlanningEngine
from engines.segmentation.placeholder import PlaceholderSegmentationEngine


def test_placeholder_segmentation_returns_fixture_labeled_teeth() -> None:
    engine = PlaceholderSegmentationEngine()
    positions = engine.segment("irrelevant/path.stl")
    assert len(positions) == 32
    fdi_numbers = {p.tooth.fdi_number for p in positions}
    assert 11 in fdi_numbers
    assert 48 in fdi_numbers


def test_placeholder_planning_marks_plan_as_fixture_and_generated() -> None:
    segmentation_engine = PlaceholderSegmentationEngine()
    planning_engine = PlaceholderPlanningEngine()

    tooth_positions = segmentation_engine.segment("irrelevant/path.stl")
    plan = planning_engine.generate_plan("case-123", tooth_positions)

    assert plan.fixture is True
    assert plan.provenance == DataProvenance.GENERATED
    assert plan.stage_count == 1
    assert plan.stages[0].fixture is True
    assert "not" in plan.notes.lower()  # documents what is missing
