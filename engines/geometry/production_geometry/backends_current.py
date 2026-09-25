"""Current Production CAD backend — finite/non-empty integrity only."""

from __future__ import annotations

import math
from time import perf_counter

from engines.geometry.production_geometry.types import (
    GeometryBackendInfo,
    GeometryOperationResult,
    MeshBuffers,
)


class CurrentIntegrityBackend:
    name = "current_integrity"
    version = "production_cad_v1"

    def info(self) -> GeometryBackendInfo:
        return GeometryBackendInfo(
            name=self.name,
            version=self.version,
            available=True,
            capabilities=("mesh_integrity_finite_nonempty",),
            limitations=(
                "Finite/non-empty checks are technical only.",
                "Does not certify manufacturing readiness.",
            ),
        )

    def inspect_integrity(self, mesh: MeshBuffers) -> GeometryOperationResult:
        started = perf_counter()
        input_hash = mesh.sha256()
        empty = not mesh.vertices or not mesh.faces
        nonfinite = 0
        for point in mesh.vertices:
            if len(point) < 3 or not all(math.isfinite(float(v)) for v in point[:3]):
                nonfinite += 1
                break
        ok = not empty and nonfinite == 0
        return GeometryOperationResult(
            operation="mesh_integrity",
            backend=self.name,
            backend_version=self.version,
            supported=True,
            success=ok,
            message=(
                "Finite non-empty triangle mesh."
                if ok
                else f"Integrity failure empty={empty} nonfinite={nonfinite > 0}."
            ),
            elapsed_ms=(perf_counter() - started) * 1000,
            input_hash=input_hash,
            metrics={"vertex_count": len(mesh.vertices), "face_count": len(mesh.faces)},
            limitations=self.info().limitations,
        )
