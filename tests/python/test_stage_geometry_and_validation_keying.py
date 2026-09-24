"""Focused tests for two issues found while investigating `_mesh_for_state`:

1. `_mesh_for_state` used `state.final_target_faces` unconditionally while `state.vertices`
   varies by stage (source at stage 0, interpolated in between, target at the final stage).
   Investigation showed source/target face topology is always identical today (both are the
   same `tooth.instance.mesh_faces` object from planning through to staging/edits), so this was
   not an *active* geometric bug — but the assumption was never encoded or checked. This file
   proves the intended per-stage representation explicitly and proves a genuine topology
   mismatch is now caught instead of silently producing wrong geometry.

2. The real, active bug found during this investigation: `GeometricValidationEngine.
   _validate_stage` built its per-tooth mesh lookup keyed by `state.tooth_number`. In
   "semantic_only_experimental" planning mode (used for every real ToothInstanceNet case),
   `tooth_number` is `None` for every tooth, so the lookup dict collapsed to a single entry and
   every one of the 91 tooth-pair combinations silently compared a tooth's mesh against *itself*
   instead of its real neighbor. This both invalidated the geometric validation result (a mesh
   always "intersects" itself) and made validation dramatically slower (comparing the largest
   real tooth mesh, ~13k faces, against itself). The fix keys the lookup by the same
   `_state_sort_key` already used for ordering (tooth_number, falling back to tooth_ref).
"""

from dataclasses import replace

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ToothCoordinateSystem
from domain.treatment_plan.setup import ToothMovement
from domain.treatment_plan.staging import StageMovement, StageToothState
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
    _mesh_for_state,
)
from tests.fixtures.synthetic_validation import cuboid_vertices, validation_result, validation_stage

AXES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
FRAME = ToothCoordinateSystem((0.0, 0.0, 0.0), *AXES)


def _semantic_only_stage(origins: tuple[tuple[float, float, float], ...]):
    """Two (or more) teeth with `tooth_number=None`, matching the real ToothInstanceNet path."""
    stage = validation_stage(origins)
    semantic_states = tuple(
        replace(
            state,
            tooth_number=None,
            tooth_ref=f"upper:instance:{index}",
            planning_mode="semantic_only_experimental",
        )
        for index, state in enumerate(stage.tooth_states)
    )
    return replace(stage, tooth_states=semantic_states)


def test_semantic_only_teeth_are_validated_against_their_real_neighbor_not_themselves() -> None:
    """Reproduces the real bug: all-None tooth_number must not collapse the mesh lookup."""
    stage = _semantic_only_stage(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))
    report = GeometricValidationEngine().validate(
        validation_result(stage), GeometricValidationConfiguration(1.0, 0.001, 0.0)
    )
    stage_result = report.stage_results[0]
    # Clearly separated cuboids: the real pair distance is 1.0 and must not intersect. The bug
    # compared a mesh against itself, which trivially "intersects" and reports distance 0.0.
    assert stage_result.collision_results[0].intersects is False
    assert stage_result.collision_results[0].measured_depth is None


def test_semantic_only_intersecting_teeth_are_still_detected() -> None:
    """The keying fix must not weaken collision detection for genuinely overlapping teeth."""
    stage = _semantic_only_stage(((0.0, 0.0, 0.0), (0.5, 0.0, 0.0)))
    report = GeometricValidationEngine().validate(
        validation_result(stage), GeometricValidationConfiguration(1.0, 0.001, 0.0)
    )
    collision = report.stage_results[0].collision_results[0]
    assert collision.intersects is True
    assert collision.measured_depth == 0.5


def test_semantic_only_and_clinical_fdi_reports_agree_for_equivalent_geometry() -> None:
    """The tooth_number-keyed path (clinical) and tooth_ref-keyed path (semantic-only) must
    reach the same geometric conclusion for identical geometry."""
    clinical_stage = validation_stage(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))
    semantic_stage = _semantic_only_stage(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))
    config = GeometricValidationConfiguration(1.1, 0.001, 0.0)
    clinical = GeometricValidationEngine().validate(validation_result(clinical_stage), config)
    semantic = GeometricValidationEngine().validate(validation_result(semantic_stage), config)
    assert clinical.stage_results[0].proximity_results[0].measured_distance == (
        semantic.stage_results[0].proximity_results[0].measured_distance
    )
    assert clinical.status == semantic.status


def _stage_tooth_state(vertices, faces, *, source_faces=None, final_target_faces=None):
    return StageToothState(
        tooth_number=None,
        tooth_ref="upper:instance:0",
        source_instance_id=0,
        source_vertices=vertices,
        source_faces=source_faces if source_faces is not None else faces,
        final_target_vertices=vertices,
        final_target_faces=final_target_faces if final_target_faces is not None else faces,
        vertices=vertices,
        coordinate_system=FRAME,
        movement=StageMovement("upper:instance:0", ToothMovement(), 0.0),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        planning_mode="semantic_only_experimental",
    )


def test_mesh_for_state_uses_source_topology_at_stage_zero() -> None:
    vertices = cuboid_vertices((0.0, 0.0, 0.0))
    source_faces = ((0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1))
    state = _stage_tooth_state(
        vertices, source_faces, source_faces=source_faces, final_target_faces=source_faces
    )
    result = _mesh_for_state(state)
    assert result.error is None
    assert len(result.mesh.faces) == len(source_faces)


def test_mesh_for_state_rejects_diverging_topology_at_interpolated_stage() -> None:
    """Proves the mismatch: an intermediate stage's vertices interpolate per-index between
    source and target, which is only geometrically valid if source and target share topology.
    A genuine divergence must fail closed, not silently reconstruct the wrong mesh."""
    source_vertices = cuboid_vertices((0.0, 0.0, 0.0))
    target_vertices = cuboid_vertices((1.0, 0.0, 0.0))
    interpolated_vertices = tuple(
        tuple(s + 0.5 * (t - s) for s, t in zip(source_vertex, target_vertex, strict=True))
        for source_vertex, target_vertex in zip(source_vertices, target_vertices, strict=True)
    )
    source_faces = ((0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1))
    diverging_target_faces = ((0, 1, 3), (0, 3, 2), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1))
    state = StageToothState(
        tooth_number=None,
        tooth_ref="upper:instance:0",
        source_instance_id=0,
        source_vertices=source_vertices,
        source_faces=source_faces,
        final_target_vertices=target_vertices,
        final_target_faces=diverging_target_faces,
        vertices=interpolated_vertices,
        coordinate_system=FRAME,
        movement=StageMovement("upper:instance:0", ToothMovement(), 0.5),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        planning_mode="semantic_only_experimental",
    )
    result = _mesh_for_state(state)
    assert result.error == "source/target face topology mismatch for interpolated stage"


def test_mesh_for_state_still_reconstructs_when_topology_matches_at_intermediate_stage() -> None:
    source_vertices = cuboid_vertices((0.0, 0.0, 0.0))
    target_vertices = cuboid_vertices((1.0, 0.0, 0.0))
    interpolated_vertices = tuple(
        tuple(s + 0.5 * (t - s) for s, t in zip(source_vertex, target_vertex, strict=True))
        for source_vertex, target_vertex in zip(source_vertices, target_vertices, strict=True)
    )
    faces = ((0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1))
    state = StageToothState(
        tooth_number=None,
        tooth_ref="upper:instance:0",
        source_instance_id=0,
        source_vertices=source_vertices,
        source_faces=faces,
        final_target_vertices=target_vertices,
        final_target_faces=faces,
        vertices=interpolated_vertices,
        coordinate_system=FRAME,
        movement=StageMovement("upper:instance:0", ToothMovement(), 0.5),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        planning_mode="semantic_only_experimental",
    )
    result = _mesh_for_state(state)
    assert result.error is None
    assert len(result.mesh.faces) == len(faces)
