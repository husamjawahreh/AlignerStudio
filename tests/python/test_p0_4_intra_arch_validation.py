"""P0.4: dual-arch staging validation is intra-arch (occlusion is out of scope)."""

from __future__ import annotations

from dataclasses import replace

from domain.treatment_plan.validation import ValidationStatus
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)
from tests.fixtures.synthetic_validation import validation_result, validation_stage
from tests.python.test_stage_geometry_and_validation_keying import _semantic_only_stage

CONFIG = GeometricValidationConfiguration(1.0, 0.001, 0.0)


def test_cross_arch_occlusal_overlap_is_not_reported_as_staging_collision() -> None:
    """Upper/lower meshes that overlap in occlusion must not inflate collision counts."""
    stage = validation_stage(((0.0, 0.0, 0.0), (0.5, 0.0, 0.0)))
    dual = replace(
        stage,
        tooth_states=(
            replace(
                stage.tooth_states[0],
                tooth_number=None,
                tooth_ref="upper:instance:0",
                arch="upper",
                planning_mode="semantic_only_experimental",
            ),
            replace(
                stage.tooth_states[1],
                tooth_number=None,
                tooth_ref="lower:instance:0",
                arch="lower",
                planning_mode="semantic_only_experimental",
            ),
        ),
    )
    report = GeometricValidationEngine().validate(validation_result(dual), CONFIG)
    result = report.stage_results[0]
    assert result.collision_results == ()
    assert result.proximity_results == ()
    assert result.contact_results == ()
    assert result.status is ValidationStatus.PASS


def test_same_arch_collisions_are_still_detected() -> None:
    stage = _semantic_only_stage(((0.0, 0.0, 0.0), (0.5, 0.0, 0.0)))
    stage = replace(
        stage,
        tooth_states=tuple(replace(state, arch="upper") for state in stage.tooth_states),
    )
    report = GeometricValidationEngine().validate(validation_result(stage), CONFIG)
    collision = report.stage_results[0].collision_results[0]
    assert collision.intersects is True
    assert collision.tooth_a == "upper:instance:0"
    assert collision.tooth_b == "upper:instance:1"


def test_same_arch_proximity_still_reported_within_threshold() -> None:
    stage = _semantic_only_stage(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))
    stage = replace(
        stage,
        tooth_states=tuple(replace(state, arch="upper") for state in stage.tooth_states),
    )
    report = GeometricValidationEngine().validate(validation_result(stage), CONFIG)
    result = report.stage_results[0]
    assert len(result.proximity_results) == 1
    assert result.proximity_results[0].status is ValidationStatus.WARNING
    assert result.collision_results[0].intersects is False
