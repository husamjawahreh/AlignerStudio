"""N4.3/N4.5: `_mesh_pair_metrics` broad+narrow phase rewrite must match the original
brute-force semantics exactly, and must scale far better than O(F1 * F2).

The reference (`_reference_mesh_pair_metrics`) below is the original pre-N4 nested-loop
implementation, kept here only as an oracle for equivalence testing; it is not used by
production code.
"""

import time

import numpy as np
import pytest
import trimesh

from engines.validation.geometric_engine import (
    _aabb_distance,
    _mesh_pair_metrics,
    _triangle_distance,
    _triangles_intersect,
)


def _reference_mesh_pair_metrics(first, second, broadphase_tolerance, intersection_tolerance):
    """Pre-N4 full cross-product scan; exact semantic reference, deliberately unoptimized."""
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


def _cube(origin: tuple[float, float, float], size: float = 1.0) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=(size, size, size)).apply_translation(
        (origin[0] + size / 2, origin[1] + size / 2, origin[2] + size / 2)
    )


def _dense_sphere(
    origin: tuple[float, float, float], radius: float, subdivisions: int
) -> trimesh.Trimesh:
    mesh = trimesh.creation.icosphere(subdivisions=subdivisions, radius=radius)
    mesh.apply_translation(origin)
    return mesh


@pytest.mark.parametrize(
    "label, first, second",
    [
        ("clearly-separated", _cube((0.0, 0.0, 0.0)), _cube((10.0, 0.0, 0.0))),
        ("non-intersecting-nearby", _cube((0.0, 0.0, 0.0)), _cube((2.0, 0.0, 0.0))),
        ("touching", _cube((0.0, 0.0, 0.0)), _cube((1.0, 0.0, 0.0))),
        ("intersecting", _cube((0.0, 0.0, 0.0)), _cube((0.5, 0.0, 0.0))),
    ],
)
def test_vectorized_matches_reference_on_representative_pairs(label, first, second) -> None:
    reference = _reference_mesh_pair_metrics(first, second, 1.0, 0.001)
    new = _mesh_pair_metrics(first, second, 1.0, 0.001)
    assert new[1] == reference[1], label
    assert new[0] == pytest.approx(reference[0], abs=1e-9), label
    assert new[2] == pytest.approx(reference[2], abs=1e-9), label


def test_vectorized_matches_reference_on_denser_real_scale_meshes() -> None:
    # Dense-enough spheres (hundreds of faces each) to exercise real candidate volumes while
    # keeping the O(F1*F2) reference tractable in a fast unit test.
    first = _dense_sphere((0.0, 0.0, 0.0), radius=1.0, subdivisions=1)
    second = _dense_sphere((2.3, 0.0, 0.0), radius=1.0, subdivisions=1)
    reference = _reference_mesh_pair_metrics(first, second, 0.5, 0.001)
    new = _mesh_pair_metrics(first, second, 0.5, 0.001)
    assert new[1] == reference[1]
    assert new[0] == pytest.approx(reference[0], abs=1e-9)
    assert new[2] == pytest.approx(reference[2], abs=1e-9)


def test_no_candidates_within_tolerance_returns_infinite_distance() -> None:
    first = _cube((0.0, 0.0, 0.0))
    second = _cube((100.0, 0.0, 0.0))
    distance, intersects, depth = _mesh_pair_metrics(first, second, 0.5, 0.001)
    assert distance == float("inf")
    assert intersects is False
    assert depth == 0.0


def test_vectorized_scales_far_better_than_full_cross_product() -> None:
    # Two moderately dense, close (but not overlapping) spheres: large enough that the
    # O(F1*F2) reference is measurably slow, while the rtree/vectorized path stays fast.
    first = _dense_sphere((0.0, 0.0, 0.0), radius=1.0, subdivisions=2)
    second = _dense_sphere((2.3, 0.0, 0.0), radius=1.0, subdivisions=2)

    started = time.perf_counter()
    new = _mesh_pair_metrics(first, second, 0.5, 0.001)
    new_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    reference = _reference_mesh_pair_metrics(first, second, 0.5, 0.001)
    reference_elapsed = time.perf_counter() - started

    assert new[1] == reference[1]
    assert new[0] == pytest.approx(reference[0], abs=1e-9)
    assert new_elapsed < reference_elapsed
