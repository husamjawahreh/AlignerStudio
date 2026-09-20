"""Deterministic mesh normalization and ONNX feature preparation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh

from engines.geometry.mesh_validation import MeshValidationResult, validate_mesh_file


class MeshPreprocessingError(ValueError):
    """Raised when a mesh cannot be prepared for inference."""


@dataclass(frozen=True)
class PreparedMesh:
    """Normalized mesh and per-face model features."""

    source_path: str
    vertices: np.ndarray
    faces: np.ndarray
    normalized_vertices: np.ndarray
    face_features: np.ndarray
    validation: MeshValidationResult


@dataclass(frozen=True)
class MeshPreprocessingConfig:
    """Engineering-only preprocessing settings; these are not clinical rules."""

    minimum_triangle_count: int = 1000
    maximum_triangle_count: int | None = 10000


def _load_triangle_mesh(mesh_path: str | Path) -> trimesh.Trimesh:
    try:
        loaded = trimesh.load(mesh_path, force="mesh")
    except Exception as exc:  # noqa: BLE001 - convert loader errors to domain-facing errors
        raise MeshPreprocessingError(f"Unable to load mesh '{mesh_path}': {exc}") from exc
    if not isinstance(loaded, trimesh.Trimesh):
        raise MeshPreprocessingError("Input did not resolve to a triangle mesh")
    if len(loaded.vertices) == 0 or len(loaded.faces) == 0:
        raise MeshPreprocessingError("Input mesh is empty")
    return loaded


def _normalize_vertices(vertices: np.ndarray) -> np.ndarray:
    centered = vertices.astype(np.float64, copy=True)
    centered -= centered.mean(axis=0, keepdims=True)
    scale = float(np.max(np.linalg.norm(centered, axis=1)))
    if not np.isfinite(scale) or scale <= 0:
        raise MeshPreprocessingError("Mesh has no finite spatial extent")
    normalized = centered / scale
    return normalized - normalized.mean(axis=0, keepdims=True)


def _build_face_features(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    face_vertices = vertices[faces]
    centroids = face_vertices.mean(axis=1)
    edge_a = face_vertices[:, 1] - face_vertices[:, 0]
    edge_b = face_vertices[:, 2] - face_vertices[:, 0]
    normals = np.cross(edge_a, edge_b)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.maximum(lengths, np.finfo(np.float32).eps)
    # MeshSegNet-compatible shape: 9 vertex values + 3 normal + 3 relative position.
    return np.concatenate(
        [face_vertices.reshape(len(faces), 9), normals, centroids], axis=1
    ).astype(np.float32)


def prepare_mesh(
    mesh_path: str | Path,
    config: MeshPreprocessingConfig | None = None,
) -> PreparedMesh:
    """Validate, normalize, and convert a mesh into deterministic face features."""
    settings = config or MeshPreprocessingConfig()
    path = Path(mesh_path)
    validation = validate_mesh_file(path)
    if not validation.is_valid and validation.triangle_count < settings.minimum_triangle_count:
        raise MeshPreprocessingError("Mesh failed validation: " + "; ".join(validation.errors))
    if (
        settings.maximum_triangle_count is not None
        and validation.triangle_count > settings.maximum_triangle_count
    ):
        raise MeshPreprocessingError(
            f"Mesh has {validation.triangle_count} triangles; maximum supported for "
            f"inference is {settings.maximum_triangle_count} (engineering limit)."
        )

    mesh = _load_triangle_mesh(path)
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    normalized_vertices = _normalize_vertices(vertices)
    face_features = _build_face_features(normalized_vertices, faces)
    return PreparedMesh(
        source_path=str(path),
        vertices=vertices,
        faces=faces,
        normalized_vertices=normalized_vertices,
        face_features=face_features,
        validation=validation,
    )
