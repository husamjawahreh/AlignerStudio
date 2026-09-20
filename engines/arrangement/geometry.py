"""Deterministic geometry helpers for identification and arch analysis."""

from __future__ import annotations

import numpy as np

from domain.tooth.identification import Matrix3, Vector3
from domain.tooth.segmentation import ToothInstance


class ToothGeometryError(ValueError):
    """Raised when a tooth cannot support geometric analysis."""


def _unit(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if not np.isfinite(length) or length <= 0:
        raise ToothGeometryError("Geometry contains a zero-length axis")
    return vector / length


def _orient(vector: np.ndarray, reference: np.ndarray) -> np.ndarray:
    dot = float(np.dot(vector, reference))
    if dot < 0:
        return -vector
    if np.isclose(dot, 0.0):
        first_nonzero = next((value for value in vector if not np.isclose(value, 0.0)), 0.0)
        return vector if first_nonzero >= 0 else -vector
    return vector


def finite_vertices(instance: ToothInstance) -> np.ndarray:
    """Return instance vertices or reject missing/malformed geometry."""
    if not instance.mesh_vertices or not instance.mesh_faces:
        raise ToothGeometryError("Tooth instance has missing mesh geometry")
    vertices = np.asarray(instance.mesh_vertices, dtype=np.float64)
    faces = np.asarray(instance.mesh_faces, dtype=np.int64)
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ToothGeometryError("Tooth vertices must have shape (N, 3)")
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise ToothGeometryError("Tooth faces must have shape (M, 3)")
    if np.any(faces < 0) or np.any(faces >= len(vertices)):
        raise ToothGeometryError("Tooth faces reference vertices outside the mesh")
    if not np.all(np.isfinite(vertices)):
        raise ToothGeometryError("Tooth vertices contain non-finite values")
    return vertices


def build_arch_axes(centroids: np.ndarray) -> Matrix3:
    """Build a stable lateral/anterior/vertical frame from arch centroids."""
    if centroids.ndim != 2 or centroids.shape[0] < 2 or centroids.shape[1] != 3:
        raise ToothGeometryError("At least two 3D centroids are required for an arch frame")
    if not np.all(np.isfinite(centroids)):
        raise ToothGeometryError("Arch centroids contain non-finite values")
    centered = centroids - centroids.mean(axis=0, keepdims=True)
    covariance = centered.T @ centered
    values, vectors = np.linalg.eigh(covariance)
    lateral = _orient(_unit(vectors[:, int(np.argmax(values))]), np.array([1.0, 0.0, 0.0]))
    vertical = _orient(_unit(vectors[:, int(np.argmin(values))]), np.array([0.0, 0.0, 1.0]))
    anterior = _unit(np.cross(vertical, lateral))
    lateral = _unit(np.cross(anterior, vertical))
    return tuple(tuple(float(value) for value in axis) for axis in (lateral, anterior, vertical))


def project(point: Vector3, origin: Vector3, axes: Matrix3) -> Vector3:
    relative = np.asarray(point, dtype=np.float64) - np.asarray(origin, dtype=np.float64)
    return tuple(float(np.dot(relative, axis)) for axis in axes)


def frame_for_instance(instance: ToothInstance, origin: Vector3, axes: Matrix3) -> Matrix3:
    """Use the arch frame as a stable local frame for a future movement pose."""
    del instance
    return axes


def landmarks_for_instance(instance: ToothInstance, axes: Matrix3):
    """Compute descriptive extrema along the stable arch frame axes."""
    vertices = finite_vertices(instance)
    centroid = vertices.mean(axis=0)
    local = (vertices - centroid) @ np.asarray(axes, dtype=np.float64).T
    lateral_index_min = int(np.argmin(local[:, 0]))
    lateral_index_max = int(np.argmax(local[:, 0]))
    vertical_index_min = int(np.argmin(local[:, 2]))
    vertical_index_max = int(np.argmax(local[:, 2]))
    points = [
        vertices[index]
        for index in (lateral_index_min, lateral_index_max, vertical_index_max, vertical_index_min)
    ]
    return tuple(tuple(float(value) for value in point) for point in [centroid, *points])
