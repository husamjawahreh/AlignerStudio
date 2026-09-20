"""Deterministic mesh-based validation for staged treatment plans."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from itertools import combinations

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


def _mesh_for_state(state: StageToothState) -> _ValidatedMesh:
    vertices = np.asarray(state.vertices, dtype=np.float64)
    faces = np.asarray(state.final_target_faces, dtype=np.int64)
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


def _mesh_pair_metrics(
    first: trimesh.Trimesh,
    second: trimesh.Trimesh,
    broadphase_tolerance: float,
    intersection_tolerance: float,
) -> tuple[float, bool, float]:
    first_triangles = np.asarray(first.triangles)
    second_triangles = np.asarray(second.triangles)
    minimum = float("inf")
    intersects = False
    for first_triangle in first_triangles:
        first_bounds = np.stack((first_triangle.min(axis=0), first_triangle.max(axis=0)))
        for second_triangle in second_triangles:
            second_bounds = np.stack((second_triangle.min(axis=0), second_triangle.max(axis=0)))
            if _aabb_distance(first_bounds, second_bounds) > max(broadphase_tolerance, 0.0):
                continue
            distance = _triangle_distance(first_triangle, second_triangle)
            minimum = min(minimum, distance)
            if _triangles_intersect(first_triangle, second_triangle, intersection_tolerance):
                intersects = True
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
        stage_results = tuple(
            self._validate_stage(stage, staging.provenance, configuration)
            for stage in staging.stages
        )
        status = _overall_status(stage.status for stage in stage_results)
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
        for first, second in combinations(sorted(states, key=lambda item: item.tooth_number), 2):
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
        ordered_states = tuple(sorted(stage.tooth_states, key=lambda item: item.tooth_number))
        meshes = {state.tooth_number: _mesh_for_state(state) for state in ordered_states}
        errors = tuple(
            f"Tooth {state.tooth_number}: {meshes[state.tooth_number].error}"
            for state in ordered_states
            if meshes[state.tooth_number].error
        )
        proximity: list[ProximityResult] = []
        collisions: list[CollisionResult] = []
        contacts: list[ContactResult] = []
        for first, second in combinations(ordered_states, 2):
            first_mesh = meshes[first.tooth_number]
            second_mesh = meshes[second.tooth_number]
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
