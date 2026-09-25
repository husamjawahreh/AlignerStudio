"""ProductionGeometryAdapter — isolates Current / trimesh / Manifold / MeshLib backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engines.geometry.production_geometry.backends_current import CurrentIntegrityBackend
from engines.geometry.production_geometry.backends_manifold import ManifoldBackend
from engines.geometry.production_geometry.backends_meshlib import MeshLibBackend
from engines.geometry.production_geometry.backends_trimesh import TrimeshInspectionBackend
from engines.geometry.production_geometry.types import (
    GeometryBackendInfo,
    GeometryOperationResult,
    MeshBuffers,
)


@dataclass(frozen=True)
class ProductionGeometryAdapter:
    """Clean boundary for Production CAD mesh operations."""

    current: CurrentIntegrityBackend
    trimesh: TrimeshInspectionBackend
    manifold: ManifoldBackend
    meshlib: MeshLibBackend

    def backend_catalog(self) -> list[dict[str, Any]]:
        infos: list[GeometryBackendInfo] = [
            self.current.info(),
            self.trimesh.info(),
            self.manifold.info(),
            self.meshlib.info(),
        ]
        return [
            {
                "name": info.name,
                "version": info.version,
                "available": info.available,
                "capabilities": list(info.capabilities),
                "limitations": list(info.limitations),
            }
            for info in infos
        ]

    def meshlib_available(self) -> bool:
        return self.meshlib.info().available

    def manifold_available(self) -> bool:
        return self.manifold.info().available

    def inspect_integrity(self, mesh: MeshBuffers) -> GeometryOperationResult:
        return self.current.inspect_integrity(mesh)

    def inspect_topology(self, mesh: MeshBuffers) -> GeometryOperationResult:
        return self.trimesh.inspect(mesh)

    def manifold_validity(self, mesh: MeshBuffers) -> GeometryOperationResult:
        return self.manifold.manifold_status(mesh)

    def self_intersections(self, mesh: MeshBuffers) -> GeometryOperationResult:
        return self.meshlib.find_self_intersections(mesh)

    def engineering_offset(
        self,
        mesh: MeshBuffers,
        *,
        distance: float,
        voxel_size: float | None = None,
    ) -> GeometryOperationResult:
        return self.meshlib.engineering_offset(
            mesh, distance=distance, voxel_size=voxel_size
        )


_ADAPTER: ProductionGeometryAdapter | None = None


def get_production_geometry_adapter() -> ProductionGeometryAdapter:
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = ProductionGeometryAdapter(
            current=CurrentIntegrityBackend(),
            trimesh=TrimeshInspectionBackend(),
            manifold=ManifoldBackend(),
            meshlib=MeshLibBackend(),
        )
    return _ADAPTER
