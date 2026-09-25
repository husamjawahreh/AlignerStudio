"""trimesh inspection backend — watertight/winding/volume (already a project dependency)."""

from __future__ import annotations

from time import perf_counter

import numpy as np
import trimesh

from engines.geometry.production_geometry.types import (
    GeometryBackendInfo,
    GeometryOperationResult,
    MeshBuffers,
)


class TrimeshInspectionBackend:
    name = "trimesh"
    version = getattr(trimesh, "__version__", None)

    def info(self) -> GeometryBackendInfo:
        return GeometryBackendInfo(
            name=self.name,
            version=self.version,
            available=True,
            capabilities=(
                "mesh_load",
                "watertight_detection",
                "winding_consistency",
                "volume_flag",
            ),
            limitations=(
                "Watertight/volume flags are geometric, not manufacturing certification.",
                "Self-intersection of a single mesh is not claimed as complete.",
            ),
        )

    def inspect(self, mesh: MeshBuffers) -> GeometryOperationResult:
        started = perf_counter()
        input_hash = mesh.sha256()
        tm = trimesh.Trimesh(
            vertices=np.asarray(mesh.vertices, dtype=np.float64),
            faces=np.asarray(mesh.faces, dtype=np.int64),
            process=False,
        )
        metrics = {
            "watertight": bool(tm.is_watertight),
            "is_volume": bool(tm.is_volume),
            "winding_consistent": bool(tm.is_winding_consistent),
            "vertex_count": int(len(tm.vertices)),
            "face_count": int(len(tm.faces)),
        }
        return GeometryOperationResult(
            operation="mesh_inspection",
            backend=self.name,
            backend_version=self.version,
            supported=True,
            success=True,
            message="trimesh geometric inspection complete.",
            elapsed_ms=(perf_counter() - started) * 1000,
            input_hash=input_hash,
            metrics=metrics,
            limitations=self.info().limitations,
        )
