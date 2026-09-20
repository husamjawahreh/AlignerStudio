from dataclasses import replace

import pytest

from domain.treatment_plan.validation import ValidationStatus
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
    GeometricValidationError,
)
from tests.fixtures.synthetic_validation import validation_result, validation_stage

CONFIG = GeometricValidationConfiguration(
    proximity_threshold=1.1,
    contact_tolerance=0.001,
    collision_tolerance=0.0,
)


def validate(origins, configuration=CONFIG):
    return GeometricValidationEngine().validate(
        validation_result(validation_stage(origins)), configuration
    )


def test_separated_teeth_have_proximity_measurement_without_collision() -> None:
    report = validate(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))
    stage = report.stage_results[0]
    assert len(stage.proximity_results) == 1
    assert stage.proximity_results[0].measured_distance == pytest.approx(1.0)
    assert stage.proximity_results[0].status is ValidationStatus.WARNING
    assert stage.collision_results[0].intersects is False
    assert stage.contact_results[0].is_contact is False


def test_touching_teeth_are_contact_without_intersection_error() -> None:
    report = validate(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
    stage = report.stage_results[0]
    assert stage.contact_results[0].is_contact is True
    assert stage.contact_results[0].measured_distance == pytest.approx(0.0)
    assert stage.collision_results[0].intersects is False
    assert report.status is ValidationStatus.WARNING


def test_intersecting_teeth_report_collision_and_depth() -> None:
    report = validate(((0.0, 0.0, 0.0), (0.5, 0.0, 0.0)))
    collision = report.stage_results[0].collision_results[0]
    assert collision.intersects is True
    assert collision.measured_depth is not None
    assert collision.measured_depth == pytest.approx(0.5)
    assert collision.status is ValidationStatus.ERROR


def test_multiple_independent_pairs_are_stably_ordered() -> None:
    report = validate(
        ((0.0, 0.0, 0.0), (0.5, 0.0, 0.0), (5.0, 0.0, 0.0), (5.5, 0.0, 0.0)),
        GeometricValidationConfiguration(0.1, 0.001, 0.0),
    )
    pairs = [(item.tooth_a, item.tooth_b) for item in report.stage_results[0].collision_results]
    assert pairs == [(11, 12), (13, 14)]


def test_invalid_geometry_is_reported_without_crashing() -> None:
    stage = validation_stage(((0.0, 0.0, 0.0), (3.0, 0.0, 0.0)))
    malformed = replace(stage.tooth_states[0], vertices=())
    malformed_stage = replace(stage, tooth_states=(malformed, stage.tooth_states[1]))
    report = GeometricValidationEngine().validate(validation_result(malformed_stage), CONFIG)
    assert report.status is ValidationStatus.INVALID
    assert "malformed" in report.stage_results[0].errors[0]


def test_threshold_configuration_changes_proximity_status() -> None:
    clear_report = validate(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        GeometricValidationConfiguration(0.5, 0.001, 0.0),
    )
    assert clear_report.stage_results[0].proximity_results == ()


def test_deterministic_report_and_provenance() -> None:
    first = validate(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
    second = validate(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
    assert first == second
    assert first.report_id == second.report_id
    assert first.provenance.value == "fixture"
    assert first.fixture is True


def test_source_geometry_is_not_mutated() -> None:
    stage = validation_stage(((0.0, 0.0, 0.0), (0.5, 0.0, 0.0)))
    source = stage.tooth_states[0].vertices
    GeometricValidationEngine().validate(validation_result(stage), CONFIG)
    assert stage.tooth_states[0].vertices == source
    assert stage.tooth_states[0].source_vertices == source


def test_invalid_thresholds_are_rejected() -> None:
    with pytest.raises(GeometricValidationError):
        GeometricValidationConfiguration(-1.0, 0.1, 0.0)
