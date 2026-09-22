"""Exact ToothInstanceNet preprocessing, isolated from the domain layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh

from adapters.toothinstancenet.contract import ToothInstanceNetConfig, ToothInstanceNetError


@dataclass(frozen=True)
class PreparedToothInstanceNetMesh:
    source_path: str
    original_vertices: np.ndarray
    original_faces: np.ndarray
    transformed_points: np.ndarray
    transformed_normals: np.ndarray
    sampled_indices: np.ndarray
    features: np.ndarray
    affine: np.ndarray


def _pose_normalize(
    points: np.ndarray, normals: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    centered = points - points.mean(axis=0, keepdims=True)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    rotation = vh
    if np.linalg.det(rotation) < 0:
        rotation = np.array([[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]) @ rotation
    rotated_normals = normals @ rotation.T
    if float(rotated_normals[:, 2].mean()) < 0:
        rotation = np.array([[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]) @ rotation
    transformed = points @ rotation.T
    transformed_normals = normals @ rotation.T
    affine = np.eye(4, dtype=np.float32)
    affine[:3, :3] = rotation.astype(np.float32)
    return transformed, transformed_normals, affine


def _uniform_density_indices(points: np.ndarray, voxel_size: float) -> np.ndarray:
    if voxel_size <= 0:
        raise ToothInstanceNetError("uniform_density_voxel_size must be positive")
    shifted = points - points.min(axis=0)
    discrete = np.floor(shifted / voxel_size).astype(np.int64)
    voxel_keys, inverse = np.unique(discrete, axis=0, return_inverse=True)
    centers = (voxel_keys.astype(np.float64) + 0.5) * voxel_size
    distances = np.sum((shifted - centers[inverse]) ** 2, axis=1)
    chosen = []
    for voxel in range(len(voxel_keys)):
        candidates = np.flatnonzero(inverse == voxel)
        chosen.append(int(candidates[np.argmin(distances[candidates])]))
    return np.asarray(chosen, dtype=np.int64)


def prepare_mesh(path: str | Path, config: ToothInstanceNetConfig) -> PreparedToothInstanceNetMesh:
    """Apply ZScoreNormalize, PoseNormalize, InstanceCentroids, downsample, XYZ and normals."""
    loaded = trimesh.load(path, force="mesh", process=False)
    if (
        not isinstance(loaded, trimesh.Trimesh)
        or len(loaded.vertices) == 0
        or len(loaded.faces) == 0
    ):
        raise ToothInstanceNetError(f"Unable to load a non-empty triangle mesh from '{path}'.")
    original_vertices = np.asarray(loaded.vertices, dtype=np.float32).copy()
    original_faces = np.asarray(loaded.faces, dtype=np.int64).copy()
    normals = np.asarray(loaded.vertex_normals, dtype=np.float32)

    points = (original_vertices - original_vertices.mean(axis=0, keepdims=True)) / config.zscore_std
    points, normals, affine = _pose_normalize(points, normals)
    sampled_indices = _uniform_density_indices(points, config.uniform_density_voxel_size)
    sampled_points = points[sampled_indices]
    sampled_normals = normals[sampled_indices]
    features = np.concatenate((sampled_points, sampled_normals), axis=1).astype(np.float32)
    return PreparedToothInstanceNetMesh(
        source_path=str(path),
        original_vertices=original_vertices,
        original_faces=original_faces,
        transformed_points=points.astype(np.float32),
        transformed_normals=normals.astype(np.float32),
        sampled_indices=sampled_indices,
        features=features,
        affine=affine,
    )
