"""Deterministic mesh geometry metrics for Dental Intelligence 2.0 (WP-02).

Computes reproducible quantities from tooth mesh vertices/faces.
Principal directions are mesh PCA — never labeled as clinical dental axes.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from domain.tooth.intelligence_v2 import GEOMETRY_ALGORITHM_VERSION, GeometryMetrics


class GeometryMetricsError(ValueError):
    """Raised when mesh geometry cannot support metrics."""


def compute_geometry_metrics(
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
) -> GeometryMetrics:
    """Compute deterministic mesh metrics. Raises GeometryMetricsError on empty/invalid mesh."""
    if not vertices or not faces:
        raise GeometryMetricsError("empty_geometry")
    verts = np.asarray(vertices, dtype=np.float64)
    tris = np.asarray(faces, dtype=np.int64)
    if verts.ndim != 2 or verts.shape[1] != 3:
        raise GeometryMetricsError("invalid_vertex_shape")
    if tris.ndim != 2 or tris.shape[1] != 3:
        raise GeometryMetricsError("invalid_face_shape")
    if np.any(tris < 0) or np.any(tris >= len(verts)):
        raise GeometryMetricsError("face_index_out_of_range")
    if not np.all(np.isfinite(verts)):
        raise GeometryMetricsError("non_finite_vertices")

    bbox_min = tuple(float(value) for value in verts.min(axis=0))
    bbox_max = tuple(float(value) for value in verts.max(axis=0))
    extents = tuple(float(hi - lo) for lo, hi in zip(bbox_min, bbox_max, strict=True))
    centroid = tuple(float(value) for value in verts.mean(axis=0))

    surface_area = _triangle_surface_area(verts, tris)
    volume = _signed_volume(verts, tris)
    # Volume is only reported when absolute volume is positive and finite.
    volume_out = float(abs(volume)) if volume is not None and math.isfinite(volume) and abs(volume) > 0 else None

    principal = _principal_directions(verts)

    return GeometryMetrics(
        vertex_count=int(len(verts)),
        face_count=int(len(tris)),
        centroid=centroid,
        bounding_box_min=bbox_min,
        bounding_box_max=bbox_max,
        extents=extents,
        surface_area=surface_area,
        volume=volume_out,
        principal_directions=principal,
        principal_directions_kind="mesh_pca",
        mesh_finite=True,
        empty_geometry=False,
    )


def _triangle_surface_area(verts: np.ndarray, tris: np.ndarray) -> float | None:
    try:
        a = verts[tris[:, 0]]
        b = verts[tris[:, 1]]
        c = verts[tris[:, 2]]
        cross = np.cross(b - a, c - a)
        areas = 0.5 * np.linalg.norm(cross, axis=1)
        total = float(np.sum(areas))
        return total if math.isfinite(total) else None
    except Exception:  # noqa: BLE001 - metrics boundary
        return None


def _signed_volume(verts: np.ndarray, tris: np.ndarray) -> float | None:
    """Signed volume via divergence theorem for closed triangle meshes."""
    try:
        a = verts[tris[:, 0]]
        b = verts[tris[:, 1]]
        c = verts[tris[:, 2]]
        volume = float(np.sum(np.einsum("ij,ij->i", a, np.cross(b, c))) / 6.0)
        return volume if math.isfinite(volume) else None
    except Exception:  # noqa: BLE001
        return None


def _principal_directions(
    verts: np.ndarray,
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]] | None:
    if len(verts) < 3:
        return None
    centered = verts - verts.mean(axis=0, keepdims=True)
    covariance = centered.T @ centered
    try:
        values, vectors = np.linalg.eigh(covariance)
    except np.linalg.LinAlgError:
        return None
    order = np.argsort(values)[::-1]
    axes = []
    for index in order:
        axis = vectors[:, int(index)]
        length = float(np.linalg.norm(axis))
        if not math.isfinite(length) or length <= 0:
            return None
        unit = axis / length
        # Stable sign: first non-near-zero component non-negative.
        first = next((float(v) for v in unit if not np.isclose(v, 0.0)), 0.0)
        if first < 0:
            unit = -unit
        axes.append(tuple(float(v) for v in unit))
    if len(axes) != 3:
        return None
    return (axes[0], axes[1], axes[2])


ALGORITHM_ID = "mesh_geometry_metrics"
ALGORITHM_VERSION = GEOMETRY_ALGORITHM_VERSION
