"""Manifold backend — robust booleans on manifold solids; validity gate for imports."""

from __future__ import annotations

from time import perf_counter

import numpy as np

from engines.geometry.production_geometry.types import (
    GeometryBackendInfo,
    GeometryOperationResult,
    MeshBuffers,
)

try:
    import manifold3d as m3d

    _MANIFOLD_AVAILABLE = True
    _MANIFOLD_VERSION = getattr(m3d, "__version__", None)
    if _MANIFOLD_VERSION is None:
        try:
            from importlib.metadata import version as _pkg_version

            _MANIFOLD_VERSION = _pkg_version("manifold3d")
        except Exception:  # noqa: BLE001
            _MANIFOLD_VERSION = "installed"
except Exception:  # noqa: BLE001
    m3d = None  # type: ignore[assignment]
    _MANIFOLD_AVAILABLE = False
    _MANIFOLD_VERSION = None


class ManifoldBackend:
    name = "manifold3d"
    version = _MANIFOLD_VERSION

    def info(self) -> GeometryBackendInfo:
        return GeometryBackendInfo(
            name=self.name,
            version=self.version,
            available=_MANIFOLD_AVAILABLE,
            capabilities=("boolean_union", "boolean_difference", "manifold_validity_gate")
            if _MANIFOLD_AVAILABLE
            else (),
            limitations=(
                "Requires oriented 2-manifold solid input; open crown meshes are rejected.",
                "No general surface-offset/shell API for open dental meshes.",
                "Boolean success is not manufacturing certification.",
            ),
        )

    def manifold_status(self, mesh: MeshBuffers) -> GeometryOperationResult:
        started = perf_counter()
        input_hash = mesh.sha256()
        if not _MANIFOLD_AVAILABLE:
            return GeometryOperationResult(
                operation="manifold_validity",
                backend=self.name,
                backend_version=self.version,
                supported=False,
                success=False,
                message="manifold3d is not available.",
                elapsed_ms=(perf_counter() - started) * 1000,
                input_hash=input_hash,
                limitations=self.info().limitations,
            )
        props = np.ascontiguousarray(mesh.vertices, dtype=np.float32)
        tris = np.ascontiguousarray(mesh.faces, dtype=np.uint32)
        man = m3d.Manifold(m3d.Mesh(vert_properties=props, tri_verts=tris))
        status = man.status()
        ok = status == m3d.Error.NoError and man.num_tri() > 0
        return GeometryOperationResult(
            operation="manifold_validity",
            backend=self.name,
            backend_version=self.version,
            supported=True,
            success=ok,
            message=f"Manifold status={status} num_tri={man.num_tri()}.",
            elapsed_ms=(perf_counter() - started) * 1000,
            input_hash=input_hash,
            metrics={"status": str(status), "num_tri": int(man.num_tri())},
            limitations=self.info().limitations,
        )

    def boolean_union_cubes(self) -> GeometryOperationResult:
        """Engineering boolean smoke test (synthetic solids, not anatomy)."""
        started = perf_counter()
        if not _MANIFOLD_AVAILABLE:
            return GeometryOperationResult(
                operation="boolean_union",
                backend=self.name,
                backend_version=self.version,
                supported=False,
                success=False,
                message="manifold3d is not available.",
                elapsed_ms=(perf_counter() - started) * 1000,
                limitations=self.info().limitations,
            )
        a = m3d.Manifold.cube([2.0, 2.0, 2.0])
        b = m3d.Manifold.sphere(1.2, 24).translate([0.8, 0.8, 0.8])
        out = a + b
        mesh = out.to_mesh()
        buffers = MeshBuffers(
            vertices=tuple(tuple(map(float, row[:3])) for row in mesh.vert_properties),
            faces=tuple(tuple(map(int, row)) for row in mesh.tri_verts),
            identity="synthetic_engineering_boolean",
        )
        return GeometryOperationResult(
            operation="boolean_union",
            backend=self.name,
            backend_version=self.version,
            supported=True,
            success=out.status() == m3d.Error.NoError,
            message="Engineering solid boolean union (synthetic geometry).",
            elapsed_ms=(perf_counter() - started) * 1000,
            output_hash=buffers.sha256(),
            output_mesh=buffers,
            metrics={"num_tri": int(out.num_tri()), "geometry_kind": "synthetic_engineering"},
            limitations=(
                "Synthetic engineering geometry — not anatomical evidence.",
                *self.info().limitations,
            ),
        )
