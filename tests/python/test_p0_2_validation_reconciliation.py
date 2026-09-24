"""P0.2: browser validation counts must match true geometric findings (not AABB slots)."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
from domain.treatment_plan.setup import ToothMovement, TreatmentObjective, TreatmentObjectiveType
from domain.treatment_plan.validation import ValidationStatus
from domain.tooth.identification import ArchType
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)
from services.api.app.treatment_sessions import TreatmentSessionStore, review_bundle
from tests.fixtures.synthetic_validation import validation_result, validation_stage
from tests.python.test_stage_geometry_and_validation_keying import _semantic_only_stage

ARTIFACT = Path(__file__).resolve().parents[2] / "official_real_case_stage2_verified_v1.zip"
CONFIG = GeometricValidationConfiguration(1.0, 0.001, 0.0)


def _finding_counts(stage_validation):
    return {
        "aabb_slots": len(stage_validation.collision_results),
        "collisions": sum(1 for item in stage_validation.collision_results if item.intersects),
        "proximity": sum(
            1 for item in stage_validation.proximity_results if item.status is ValidationStatus.WARNING
        ),
        "contacts": sum(1 for item in stage_validation.contact_results if item.is_contact),
    }


def test_review_bundle_does_not_count_non_intersecting_aabb_slots_as_collisions() -> None:
    report = GeometricValidationEngine().validate(
        validation_result(validation_stage(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))),
        CONFIG,
    )
    stage = report.stage_results[0]
    counts = _finding_counts(stage)
    assert counts["aabb_slots"] == 1
    assert counts["collisions"] == 0
    assert counts["proximity"] == 1
    assert counts["contacts"] == 0


def test_review_bundle_counts_true_intersections_as_collisions() -> None:
    report = GeometricValidationEngine().validate(
        validation_result(validation_stage(((0.0, 0.0, 0.0), (0.5, 0.0, 0.0)))),
        CONFIG,
    )
    stage = report.stage_results[0]
    counts = _finding_counts(stage)
    assert counts["collisions"] == 1
    assert stage.collision_results[0].intersects is True


def test_semantic_pair_ids_use_tooth_ref_not_none() -> None:
    report = GeometricValidationEngine().validate(
        validation_result(_semantic_only_stage(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))),
        CONFIG,
    )
    pair = report.stage_results[0].collision_results[0]
    assert pair.tooth_a == "upper:instance:0"
    assert pair.tooth_b == "upper:instance:1"
    assert pair.intersects is False
    tooth_keys = {item.tooth_number for item in report.stage_results[0].tooth_results}
    assert tooth_keys == {"upper:instance:0", "upper:instance:1"}
    # Per-tooth aggregation must not attach every pair to every tooth.
    for tooth in report.stage_results[0].tooth_results:
        assert len(tooth.collision_results) == 1
        assert tooth.tooth_number in (tooth.collision_results[0].tooth_a, tooth.collision_results[0].tooth_b)


def test_real_upper_fixture_browser_and_benchmark_agree(monkeypatch) -> None:
    """Same upper-only path as N4.7: intersections 0; browser DTO reports collisions 0."""
    if not ARTIFACT.is_file():
        pytest.skip("real artifact unavailable")

    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE", str(ARTIFACT))
    monkeypatch.setenv("ALIGNERSTUDIO_STAGE_COUNT", "2")

    from app.toothinstancenet_configuration import load_validated_fixture_result

    reviewed = load_validated_fixture_result(ArchType.UPPER)
    treatment_input = TreatmentPlanningInput.from_identification(
        reviewed.identification,
        diagnostics=(),
        planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL,
    )
    refs = [tooth.tooth_ref for tooth in reviewed.identification.teeth]
    objectives = (
        TreatmentObjective(
            "p0-2",
            TreatmentObjectiveType.ALIGNMENT,
            "reconciliation",
            ((refs[0], ToothMovement(translation_x=0.2)),),
        ),
    )
    session = TreatmentSessionStore().create_from_treatment_input(
        "p0-2-upper", treatment_input, objectives
    )
    stage_validation = session.validation.stage_results[0]
    engine_counts = _finding_counts(stage_validation)
    close_pairs = engine_counts["aabb_slots"]

    # N4.7 benchmark semantics on the real raw/upper fixture path.
    assert 0 < close_pairs < 91
    assert engine_counts["collisions"] == 0

    bundle = review_bundle(session)
    browser = bundle["stages"][0]
    assert browser["collisionCount"] == engine_counts["collisions"] == 0
    assert browser["proximityCount"] == engine_counts["proximity"]
    assert browser["contactCount"] == engine_counts["contacts"]
    # Previously the browser wrongly showed collisionCount == close_pairs (~13).
    assert browser["collisionCount"] != close_pairs
    assert all(
        isinstance(item.tooth_a, str) and str(item.tooth_a).startswith("upper:")
        for item in stage_validation.collision_results
    )
