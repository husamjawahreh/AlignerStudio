"""Mesh validation for uploaded STL scans.

Thresholds used here are file-sanity checks, NOT clinical thresholds — see
CLINICAL_BOUNDARIES.md (MESH-001, MESH-002, MESH-003) for sourcing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import trimesh

MIN_TRIANGLE_COUNT = 1000  # CLINICAL_BOUNDARIES.md: MESH-001 (non-clinical, file-sanity only)


@dataclass(frozen=True)
class MeshValidationResult:
    """Outcome of validating a single uploaded mesh file."""

    is_valid: bool
    triangle_count: int
    is_watertight: bool
    errors: tuple[str, ...] = field(default_factory=tuple)


def validate_mesh_file(file_path: str | Path) -> MeshValidationResult:
    """Load and validate an STL file for basic structural sanity.

    Does not perform clinical assessment of the scan — only confirms the
    file is a loadable, non-trivial triangle mesh (MESH-001, MESH-002).
    Watertightness is reported informationally (MESH-003) and does not by
    itself invalidate the mesh in Phase 1.
    """
    path = Path(file_path)
    errors: list[str] = []

    if not path.exists():
        return MeshValidationResult(
            is_valid=False,
            triangle_count=0,
            is_watertight=False,
            errors=(f"File not found: {path}",),
        )

    try:
        mesh = trimesh.load(path, force="mesh")
    except Exception as exc:  # noqa: BLE001 - surface any loader failure as a validation error
        return MeshValidationResult(
            is_valid=False,
            triangle_count=0,
            is_watertight=False,
            errors=(f"Failed to load mesh: {exc}",),
        )

    if not isinstance(mesh, trimesh.Trimesh):
        return MeshValidationResult(
            is_valid=False,
            triangle_count=0,
            is_watertight=False,
            errors=("Loaded file did not resolve to a single triangle mesh.",),
        )

    triangle_count = len(mesh.faces)
    is_watertight = bool(mesh.is_watertight)

    if triangle_count < MIN_TRIANGLE_COUNT:
        errors.append(
            f"Triangle count {triangle_count} is below minimum {MIN_TRIANGLE_COUNT} "
            "(file-sanity check, not a clinical threshold)."
        )

    if not is_watertight:
        errors.append("Mesh is not watertight (informational; not blocking in Phase 1).")

    is_valid = triangle_count >= MIN_TRIANGLE_COUNT

    return MeshValidationResult(
        is_valid=is_valid,
        triangle_count=triangle_count,
        is_watertight=is_watertight,
        errors=tuple(errors),
    )
