"""Deterministic mesh-based validation for staged treatment plans."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from itertools import combinations
from time import perf_counter

import numpy as np
import trimesh

from domain.treatment_plan.staging import StageToothState, StagingResult
from domain.treatment_plan.validation import (
    CollisionResult,
    ContactResult,
    ProximityResult,
    StageValidationResult,
    ToothValidationResult,
    TreatmentValidationReport,
    ValidationStatus,
)
from engines.validation.hooks import ValidationFinding

logger = logging.getLogger(__name__)


class GeometricValidationError(ValueError):
    """Raised for invalid validation configuration."""


@dataclass(frozen=True)
class GeometricValidationConfiguration:
    """Caller-supplied geometric thresholds; no clinical defaults exist."""

    proximity_threshold: float
    contact_tolerance: float
    collision_tolerance: float
    engine_version: str = "phase7-geometric-validation-1"

    def __post_init__(self) -> None:
        values = (
            self.proximity_threshold,
            self.contact_tolerance,
            self.collision_tolerance,
        )
        if not all(np.isfinite(value) and value >= 0.0 for value in values):
            raise GeometricValidationError("Validation thresholds must be finite and non-negative")
        if not self.engine_version.strip():
            raise GeometricValidationError("engine_version must not be empty")


@dataclass(frozen=True)
class _ValidatedMesh:
    mesh: trimesh.Trimesh
    error: str | None = None


def _state_sort_key(state: StageToothState) -> str:
    """Order clinical FDI and semantic-only states deterministically."""
    return str(state.tooth_number if state.tooth_number is not None else state.tooth_ref)


def _faces_for_state(state: StageToothState) -> tuple[tuple[int, int, int], ...] | None:
    """Select the face topology matching the vertex source actually used at this stage.

    Stage 0 uses `source_vertices` verbatim, the final stage uses `final_target_vertices`
    verbatim, and every stage in between linearly interpolates per vertex index between the
    two — which is only geometrically valid when source and target share identical face
    topology. Returns None if an intermediate stage's source/target topology diverges.
    """
    if state.vertices == state.source_vertices:
        return state.source_faces
    if state.vertices == state.final_target_vertices:
        return state.final_target_faces
    if state.source_faces == state.final_target_faces:
        return state.source_faces
    return None


def _mesh_for_state(state: StageToothState) -> _ValidatedMesh:
    vertices = np.asarray(state.vertices, dtype=np.float64)
    faces_source = _faces_for_state(state)
    if faces_source is None:
        return _ValidatedMesh(
            _empty_mesh(), "source/target face topology mismatch for interpolated stage"
        )
    faces = np.asarray(faces_source, dtype=np.int64)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) == 0:
        return _ValidatedMesh(_empty_mesh(), "empty or malformed vertex array")
    if faces.ndim != 2 or faces.shape[1] != 3 or len(faces) == 0:
        return _ValidatedMesh(_empty_mesh(), "empty or malformed face array")
    if not np.all(np.isfinite(vertices)):
        return _ValidatedMesh(_empty_mesh(), "non-finite vertex coordinate")
    if np.any(faces < 0) or np.any(faces >= len(vertices)):
        return _ValidatedMesh(_empty_mesh(), "face references an invalid vertex")
    face_vertices = vertices[faces]
    areas = np.linalg.norm(
        np.cross(
            face_vertices[:, 1] - face_vertices[:, 0], face_vertices[:, 2] - face_vertices[:, 0]
        ),
        axis=1,
    )
    if np.any(areas <= np.finfo(float).eps):
        return _ValidatedMesh(_empty_mesh(), "degenerate triangle")
    return _ValidatedMesh(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))


def _empty_mesh() -> trimesh.Trimesh:
    return trimesh.Trimesh(
        vertices=np.empty((0, 3)), faces=np.empty((0, 3), dtype=np.int64), process=False
    )


def _aabb_distance(first: np.ndarray, second: np.ndarray) -> float:
    lower_gap = np.maximum(first[0] - second[1], second[0] - first[1])
    return float(np.linalg.norm(np.maximum(lower_gap, 0.0)))


def _point_segment_distance(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
    direction = end - start
    length_squared = float(np.dot(direction, direction))
    if length_squared <= np.finfo(float).eps:
        return float(np.linalg.norm(point - start))
    amount = np.clip(float(np.dot(point - start, direction) / length_squared), 0.0, 1.0)
    return float(np.linalg.norm(point - (start + amount * direction)))


def _point_triangle_distance(point: np.ndarray, triangle: np.ndarray) -> float:
    edge_a = triangle[1] - triangle[0]
    edge_b = triangle[2] - triangle[0]
    offset = point - triangle[0]
    dot_aa = np.dot(edge_a, edge_a)
    dot_ab = np.dot(edge_a, edge_b)
    dot_ap = np.dot(edge_a, offset)
    dot_bb = np.dot(edge_b, edge_b)
    dot_bp = np.dot(edge_b, offset)
    denominator = dot_aa * dot_bb - dot_ab * dot_ab
    if denominator <= np.finfo(float).eps:
        return min(
            _point_segment_distance(point, triangle[0], triangle[1]),
            _point_segment_distance(point, triangle[1], triangle[2]),
            _point_segment_distance(point, triangle[2], triangle[0]),
        )
    u = (dot_bb * dot_ap - dot_ab * dot_bp) / denominator
    v = (dot_aa * dot_bp - dot_ab * dot_ap) / denominator
    if u >= 0 and v >= 0 and u + v <= 1:
        projection = triangle[0] + u * edge_a + v * edge_b
        return float(np.linalg.norm(point - projection))
    return min(
        _point_segment_distance(point, triangle[0], triangle[1]),
        _point_segment_distance(point, triangle[1], triangle[2]),
        _point_segment_distance(point, triangle[2], triangle[0]),
    )


def _segment_segment_distance(first_start, first_end, second_start, second_end) -> float:
    first = first_end - first_start
    second = second_end - second_start
    between = first_start - second_start
    a = float(np.dot(first, first))
    b = float(np.dot(first, second))
    c = float(np.dot(second, second))
    d = float(np.dot(first, between))
    e = float(np.dot(second, between))
    denominator = a * c - b * b
    if denominator <= np.finfo(float).eps:
        return min(
            _point_segment_distance(first_start, second_start, second_end),
            _point_segment_distance(first_end, second_start, second_end),
        )
    s = np.clip((b * e - c * d) / denominator, 0.0, 1.0)
    t = np.clip((a * e - b * d) / denominator, 0.0, 1.0)
    return float(np.linalg.norm((first_start + s * first) - (second_start + t * second)))


def _triangle_distance(first: np.ndarray, second: np.ndarray) -> float:
    distances = [_point_triangle_distance(vertex, second) for vertex in first] + [
        _point_triangle_distance(vertex, first) for vertex in second
    ]
    for first_index, second_index in ((0, 1), (1, 2), (2, 0)):
        for second_first, second_second in ((0, 1), (1, 2), (2, 0)):
            distances.append(
                _segment_segment_distance(
                    first[first_index],
                    first[second_index],
                    second[second_first],
                    second[second_second],
                )
            )
    return min(distances)


def _segment_triangle_intersects(
    start: np.ndarray, end: np.ndarray, triangle: np.ndarray, tolerance: float
) -> bool:
    direction = end - start
    edge_a = triangle[1] - triangle[0]
    edge_b = triangle[2] - triangle[0]
    cross = np.cross(direction, edge_b)
    determinant = float(np.dot(edge_a, cross))
    if abs(determinant) <= tolerance:
        return (
            min(_point_triangle_distance(start, triangle), _point_triangle_distance(end, triangle))
            <= tolerance
        )
    inverse = 1.0 / determinant
    offset = start - triangle[0]
    u = inverse * float(np.dot(offset, cross))
    if u < -tolerance or u > 1.0 + tolerance:
        return False
    direction_cross = np.cross(offset, edge_a)
    v = inverse * float(np.dot(direction, direction_cross))
    if v < -tolerance or u + v > 1.0 + tolerance:
        return False
    distance = inverse * float(np.dot(edge_b, direction_cross))
    return -tolerance <= distance <= 1.0 + tolerance


def _triangles_intersect(first: np.ndarray, second: np.ndarray, tolerance: float) -> bool:
    for start, end in ((first[0], first[1]), (first[1], first[2]), (first[2], first[0])):
        if _segment_triangle_intersects(start, end, second, tolerance):
            return True
    for start, end in ((second[0], second[1]), (second[1], second[2]), (second[2], second[0])):
        if _segment_triangle_intersects(start, end, first, tolerance):
            return True
    return _triangle_distance(first, second) <= tolerance


def _dot_rows(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    return np.einsum("ij,ij->i", first, second)


def _point_segment_distance_batch(
    points: np.ndarray, starts: np.ndarray, ends: np.ndarray
) -> np.ndarray:
    """Batched equivalent of `_point_segment_distance`; identical formula, N pairs at once."""
    direction = ends - starts
    length_squared = _dot_rows(direction, direction)
    eps = np.finfo(float).eps
    degenerate = length_squared <= eps
    safe_length_squared = np.where(degenerate, 1.0, length_squared)
    amount = np.clip(_dot_rows(points - starts, direction) / safe_length_squared, 0.0, 1.0)
    projected = starts + amount[:, None] * direction
    return np.where(
        degenerate,
        np.linalg.norm(points - starts, axis=1),
        np.linalg.norm(points - projected, axis=1),
    )


def _point_triangle_distance_batch(points: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Batched equivalent of `_point_triangle_distance`; identical formula, N pairs at once."""
    edge_a = triangles[:, 1] - triangles[:, 0]
    edge_b = triangles[:, 2] - triangles[:, 0]
    offset = points - triangles[:, 0]
    dot_aa = _dot_rows(edge_a, edge_a)
    dot_ab = _dot_rows(edge_a, edge_b)
    dot_ap = _dot_rows(edge_a, offset)
    dot_bb = _dot_rows(edge_b, edge_b)
    dot_bp = _dot_rows(edge_b, offset)
    denominator = dot_aa * dot_bb - dot_ab * dot_ab
    eps = np.finfo(float).eps
    degenerate = denominator <= eps
    safe_denominator = np.where(degenerate, 1.0, denominator)
    u = (dot_bb * dot_ap - dot_ab * dot_bp) / safe_denominator
    v = (dot_aa * dot_bp - dot_ab * dot_ap) / safe_denominator
    inside = (u >= 0) & (v >= 0) & (u + v <= 1)
    projection = triangles[:, 0] + u[:, None] * edge_a + v[:, None] * edge_b
    projected_distance = np.linalg.norm(points - projection, axis=1)
    edge_distance = np.minimum(
        np.minimum(
            _point_segment_distance_batch(points, triangles[:, 0], triangles[:, 1]),
            _point_segment_distance_batch(points, triangles[:, 1], triangles[:, 2]),
        ),
        _point_segment_distance_batch(points, triangles[:, 2], triangles[:, 0]),
    )
    return np.where(degenerate, edge_distance, np.where(inside, projected_distance, edge_distance))


def _segment_segment_distance_batch(
    first_starts: np.ndarray,
    first_ends: np.ndarray,
    second_starts: np.ndarray,
    second_ends: np.ndarray,
) -> np.ndarray:
    """Batched equivalent of `_segment_segment_distance`; identical formula, N pairs at once."""
    first = first_ends - first_starts
    second = second_ends - second_starts
    between = first_starts - second_starts
    a = _dot_rows(first, first)
    b = _dot_rows(first, second)
    c = _dot_rows(second, second)
    d = _dot_rows(first, between)
    e = _dot_rows(second, between)
    denominator = a * c - b * b
    eps = np.finfo(float).eps
    degenerate = denominator <= eps
    safe_denominator = np.where(degenerate, 1.0, denominator)
    s = np.clip((b * e - c * d) / safe_denominator, 0.0, 1.0)
    t = np.clip((a * e - b * d) / safe_denominator, 0.0, 1.0)
    general = np.linalg.norm(
        (first_starts + s[:, None] * first) - (second_starts + t[:, None] * second), axis=1
    )
    fallback = np.minimum(
        _point_segment_distance_batch(first_starts, second_starts, second_ends),
        _point_segment_distance_batch(first_ends, second_starts, second_ends),
    )
    return np.where(degenerate, fallback, general)


_TRIANGLE_EDGES = ((0, 1), (1, 2), (2, 0))


def _triangle_distance_batch(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Batched equivalent of `_triangle_distance`; identical 6+9 sub-distances, N pairs at once."""
    distances = [_point_triangle_distance_batch(first[:, index], second) for index in range(3)]
    distances += [_point_triangle_distance_batch(second[:, index], first) for index in range(3)]
    for first_index, first_next in _TRIANGLE_EDGES:
        for second_index, second_next in _TRIANGLE_EDGES:
            distances.append(
                _segment_segment_distance_batch(
                    first[:, first_index],
                    first[:, first_next],
                    second[:, second_index],
                    second[:, second_next],
                )
            )
    return np.min(np.stack(distances, axis=1), axis=1)


def _segment_triangle_intersects_batch(
    starts: np.ndarray, ends: np.ndarray, triangles: np.ndarray, tolerance: float
) -> np.ndarray:
    """Batched equivalent of `_segment_triangle_intersects`; identical algebra, N pairs at once."""
    direction = ends - starts
    edge_a = triangles[:, 1] - triangles[:, 0]
    edge_b = triangles[:, 2] - triangles[:, 0]
    cross = np.cross(direction, edge_b)
    determinant = _dot_rows(edge_a, cross)
    near_parallel = np.abs(determinant) <= tolerance
    safe_determinant = np.where(near_parallel, 1.0, determinant)
    inverse = 1.0 / safe_determinant
    offset = starts - triangles[:, 0]
    u = inverse * _dot_rows(offset, cross)
    direction_cross = np.cross(offset, edge_a)
    v = inverse * _dot_rows(direction, direction_cross)
    distance = inverse * _dot_rows(edge_b, direction_cross)
    valid = (
        (u >= -tolerance)
        & (u <= 1.0 + tolerance)
        & (v >= -tolerance)
        & (u + v <= 1.0 + tolerance)
        & (distance >= -tolerance)
        & (distance <= 1.0 + tolerance)
    )
    parallel_hit = (
        np.minimum(
            _point_triangle_distance_batch(starts, triangles),
            _point_triangle_distance_batch(ends, triangles),
        )
        <= tolerance
    )
    return np.where(near_parallel, parallel_hit, valid)


def _triangles_intersect_batch(
    first: np.ndarray, second: np.ndarray, tolerance: float
) -> np.ndarray:
    """Batched equivalent of `_triangles_intersect`; identical edge/fallback checks, N at once."""
    intersects = np.zeros(len(first), dtype=bool)
    for start_index, end_index in _TRIANGLE_EDGES:
        intersects |= _segment_triangle_intersects_batch(
            first[:, start_index], first[:, end_index], second, tolerance
        )
    for start_index, end_index in _TRIANGLE_EDGES:
        intersects |= _segment_triangle_intersects_batch(
            second[:, start_index], second[:, end_index], first, tolerance
        )
    intersects |= _triangle_distance_batch(first, second) <= tolerance
    return intersects


def _mesh_pair_metrics(
    first: trimesh.Trimesh,
    second: trimesh.Trimesh,
    broadphase_tolerance: float,
    intersection_tolerance: float,
) -> tuple[float, bool, float]:
    """Exact narrow-phase distance/intersection, restricted to rtree-filtered candidate pairs.

    Candidate generation uses a per-triangle rtree broad-phase (superset, then re-confirmed with
    the same `_aabb_distance` gate the original full cross-product scan used) instead of a full
    cross-product scan. Narrow-phase math is the same `_triangle_distance`/`_triangles_intersect`
    algebra, evaluated in numpy-vectorized batches instead of one Python call per pair; the
    scalar functions above remain the semantic reference and are covered by equivalence tests.
    """
    first_triangles = np.asarray(first.triangles)
    second_triangles = np.asarray(second.triangles)
    tolerance = max(broadphase_tolerance, 0.0)
    second_tree = second.triangles_tree
    first_indices: list[int] = []
    second_indices: list[int] = []
    for first_index, first_triangle in enumerate(first_triangles):
        first_bounds = np.stack((first_triangle.min(axis=0), first_triangle.max(axis=0)))
        query_bounds = (
            float(first_bounds[0, 0] - tolerance),
            float(first_bounds[0, 1] - tolerance),
            float(first_bounds[0, 2] - tolerance),
            float(first_bounds[1, 0] + tolerance),
            float(first_bounds[1, 1] + tolerance),
            float(first_bounds[1, 2] + tolerance),
        )
        for second_index in second_tree.intersection(query_bounds):
            second_triangle = second_triangles[second_index]
            second_bounds = np.stack((second_triangle.min(axis=0), second_triangle.max(axis=0)))
            if _aabb_distance(first_bounds, second_bounds) > tolerance:
                continue
            first_indices.append(first_index)
            second_indices.append(second_index)
    if not first_indices:
        return float("inf"), False, 0.0
    first_batch = first_triangles[np.asarray(first_indices)]
    second_batch = second_triangles[np.asarray(second_indices)]
    distances = _triangle_distance_batch(first_batch, second_batch)
    intersect_flags = _triangles_intersect_batch(first_batch, second_batch, intersection_tolerance)
    minimum = float(np.min(distances))
    intersects = bool(np.any(intersect_flags))
    depth = 0.0
    if intersects:
        overlap_lower = np.maximum(first.bounds[0], second.bounds[0])
        overlap_upper = np.minimum(first.bounds[1], second.bounds[1])
        depth = float(np.min(overlap_upper - overlap_lower))
    measured_depth = max(depth, 0.0)
    return minimum, intersects and measured_depth > intersection_tolerance, measured_depth


@dataclass(frozen=True)
class GeometricValidationEngine:
    """Validates every staged mesh pair without mutating stage data."""

    def validate(
        self,
        staging: StagingResult,
        configuration: GeometricValidationConfiguration,
    ) -> TreatmentValidationReport:
        started = perf_counter()
        stage_results = tuple(
            self._validate_stage(stage, staging.provenance, configuration)
            for stage in staging.stages
        )
        status = _overall_status(stage.status for stage in stage_results)
        logger.info(
            "GEOMETRIC_VALIDATION_STAGES_COMPLETED plan_id=%s duration_ms=%.1f stages=%d "
            "proximity=%d collisions=%d contacts=%d",
            staging.plan_id,
            (perf_counter() - started) * 1000,
            len(stage_results),
            sum(len(stage.proximity_results) for stage in stage_results),
            sum(len(stage.collision_results) for stage in stage_results),
            sum(len(stage.contact_results) for stage in stage_results),
        )
        payload = json.dumps(
            {
                "plan_id": staging.plan_id,
                "engine_version": configuration.engine_version,
                "stages": [
                    (stage.stage_index, stage.stage_id, stage.status.value)
                    for stage in stage_results
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return TreatmentValidationReport(
            plan_id=staging.plan_id,
            report_id=hashlib.sha256(payload.encode()).hexdigest(),
            stage_results=stage_results,
            status=status,
            provenance=staging.provenance,
            fixture=staging.fixture,
            warnings=tuple(warning for stage in stage_results for warning in stage.warnings),
            errors=tuple(error for stage in stage_results for error in stage.errors),
        )

    def detect(self, states: tuple[StageToothState, ...]) -> tuple[ValidationFinding, ...]:
        """Hook-compatible collision report using an explicit zero tolerance."""
        findings: list[ValidationFinding] = []
        for first, second in combinations(sorted(states, key=_state_sort_key), 2):
            first_mesh = _mesh_for_state(first)
            second_mesh = _mesh_for_state(second)
            if first_mesh.error or second_mesh.error:
                continue
            _, intersects, _ = _mesh_pair_metrics(first_mesh.mesh, second_mesh.mesh, 0.0, 0.0)
            if intersects:
                findings.append(
                    ValidationFinding(
                        "mesh_intersection",
                        f"Teeth {first.tooth_number} and {second.tooth_number} intersect.",
                        blocking=True,
                    )
                )
        return tuple(findings)

    def _validate_stage(self, stage, provenance, configuration):
        started = perf_counter()
        ordered_states = tuple(sorted(stage.tooth_states, key=_state_sort_key))
        # tooth_number is None for every tooth in semantic-only-experimental mode; keying by it
        # would collapse all teeth to one mesh entry and silently compare a tooth against itself.
        meshes = {_state_sort_key(state): _mesh_for_state(state) for state in ordered_states}
        errors = tuple(
            f"Tooth {_state_sort_key(state)}: {meshes[_state_sort_key(state)].error}"
            for state in ordered_states
            if meshes[_state_sort_key(state)].error
        )
        proximity: list[ProximityResult] = []
        collisions: list[CollisionResult] = []
        contacts: list[ContactResult] = []
        for first, second in combinations(ordered_states, 2):
            first_mesh = meshes[_state_sort_key(first)]
            second_mesh = meshes[_state_sort_key(second)]
            if first_mesh.error or second_mesh.error:
                continue
            if _aabb_distance(first_mesh.mesh.bounds, second_mesh.mesh.bounds) > max(
                configuration.proximity_threshold,
                configuration.contact_tolerance,
                configuration.collision_tolerance,
            ):
                continue
            distance, intersects, depth = _mesh_pair_metrics(
                first_mesh.mesh,
                second_mesh.mesh,
                max(
                    configuration.proximity_threshold,
                    configuration.contact_tolerance,
                    configuration.collision_tolerance,
                ),
                configuration.collision_tolerance,
            )
            pair_key = f"{stage.stage_index}:{first.tooth_number}:{second.tooth_number}"
            pair_id = hashlib.sha256(pair_key.encode()).hexdigest()
            proximity.append(
                ProximityResult(
                    stage.stage_index,
                    first.tooth_number,
                    second.tooth_number,
                    distance,
                    configuration.proximity_threshold,
                    ValidationStatus.WARNING
                    if distance <= configuration.proximity_threshold
                    else ValidationStatus.PASS,
                    provenance,
                    pair_id + ":proximity",
                )
            )
            collisions.append(
                CollisionResult(
                    stage.stage_index,
                    first.tooth_number,
                    second.tooth_number,
                    intersects,
                    depth if intersects else None,
                    configuration.collision_tolerance,
                    ValidationStatus.ERROR if intersects else ValidationStatus.PASS,
                    provenance,
                    pair_id + ":collision",
                )
            )
            contacts.append(
                ContactResult(
                    stage.stage_index,
                    first.tooth_number,
                    second.tooth_number,
                    distance <= configuration.contact_tolerance,
                    distance,
                    configuration.contact_tolerance,
                    ValidationStatus.WARNING
                    if distance <= configuration.contact_tolerance
                    else ValidationStatus.PASS,
                    provenance,
                    pair_id + ":contact",
                )
            )
        tooth_results = tuple(
            ToothValidationResult(
                stage.stage_index,
                state.tooth_number,
                tuple(
                    item for item in proximity if state.tooth_number in (item.tooth_a, item.tooth_b)
                ),
                tuple(
                    item
                    for item in collisions
                    if state.tooth_number in (item.tooth_a, item.tooth_b)
                ),
                tuple(
                    item for item in contacts if state.tooth_number in (item.tooth_a, item.tooth_b)
                ),
                _overall_status(
                    item.status
                    for item in (
                        *[
                            result
                            for result in collisions
                            if state.tooth_number in (result.tooth_a, result.tooth_b)
                        ],
                        *[
                            result
                            for result in proximity
                            if state.tooth_number in (result.tooth_a, result.tooth_b)
                        ],
                    )
                ),
                provenance,
            )
            for state in ordered_states
        )
        status = (
            ValidationStatus.INVALID
            if errors
            else _overall_status(item.status for item in (*proximity, *collisions, *contacts))
        )
        logger.info(
            "GEOMETRIC_VALIDATION_STAGE_COMPLETED stage_index=%d duration_ms=%.1f "
            "pairs_evaluated=%d proximity_warnings=%d collisions=%d contacts=%d status=%s",
            stage.stage_index,
            (perf_counter() - started) * 1000,
            len(proximity),
            sum(1 for item in proximity if item.status is ValidationStatus.WARNING),
            sum(1 for item in collisions if item.intersects),
            sum(1 for item in contacts if item.is_contact),
            status.value,
        )
        return StageValidationResult(
            stage.stage_index,
            stage.stage_id,
            tooth_results,
            tuple(proximity),
            tuple(collisions),
            tuple(contacts),
            status,
            provenance,
            errors=errors,
        )


def _overall_status(statuses) -> ValidationStatus:
    values = tuple(statuses)
    if any(status is ValidationStatus.INVALID for status in values):
        return ValidationStatus.INVALID
    if any(status is ValidationStatus.ERROR for status in values):
        return ValidationStatus.ERROR
    if any(status is ValidationStatus.WARNING for status in values):
        return ValidationStatus.WARNING
    return ValidationStatus.PASS
