"""MeshLib backend — offset/shell, self-intersection, boolean (optional dependency)."""

from __future__ import annotations

from time import perf_counter

import numpy as np

from engines.geometry.production_geometry.types import (
    GeometryBackendInfo,
    GeometryOperationResult,
    MeshBuffers,
)

try:
    from meshlib import mrmeshnumpy as mn
    from meshlib import mrmeshpy as mm

    _MESHLIB_AVAILABLE = True
    try:
        from importlib.metadata import version as _pkg_version

        _MESHLIB_VERSION = _pkg_version("meshlib")
    except Exception:  # noqa: BLE001
        _MESHLIB_VERSION = "installed"
except Exception:  # noqa: BLE001
    mm = None  # type: ignore[assignment]
    mn = None  # type: ignore[assignment]
    _MESHLIB_AVAILABLE = False
    _MESHLIB_VERSION = None


class MeshLibBackend:
    name = "meshlib"
    version = _MESHLIB_VERSION

    def info(self) -> GeometryBackendInfo:
        return GeometryBackendInfo(
            name=self.name,
            version=self.version,
            available=_MESHLIB_AVAILABLE,
            capabilities=(
                "engineering_offset",
                "self_intersection_query",
                "boolean_union",
                "watertight_rebuild_via_offset",
            )
            if _MESHLIB_AVAILABLE
            else (),
            limitations=(
                "Offset uses voxelization; resolution depends on voxelSize.",
                "Engineering offset is not manufacturing certification or clinical approval.",
                "Trimline and material thickness profiles are not provided by this backend.",
            ),
        )

    def _to_meshlib(self, mesh: MeshBuffers):
        faces = np.asarray(mesh.faces, dtype=np.int32)
        verts = np.asarray(mesh.vertices, dtype=np.float32)
        return mn.meshFromFacesVerts(faces, verts)

    def _from_meshlib(self, mesh) -> MeshBuffers:
        verts = mn.getNumpyVerts(mesh)
        faces = mn.getNumpyFaces(mesh.topology)
        return MeshBuffers(
            vertices=tuple(tuple(map(float, row)) for row in verts),
            faces=tuple(tuple(map(int, row)) for row in faces),
        )

    def find_self_intersections(self, mesh: MeshBuffers) -> GeometryOperationResult:
        started = perf_counter()
        input_hash = mesh.sha256()
        if not _MESHLIB_AVAILABLE:
            return GeometryOperationResult(
                operation="self_intersection",
                backend=self.name,
                backend_version=self.version,
                supported=False,
                success=False,
                message="meshlib is not available.",
                elapsed_ms=(perf_counter() - started) * 1000,
                input_hash=input_hash,
                limitations=self.info().limitations,
            )
        ml = self._to_meshlib(mesh)
        hits = mm.findSelfCollidingTriangles(ml)
        count = len(hits) if hasattr(hits, "__len__") else int(hits)
        return GeometryOperationResult(
            operation="self_intersection",
            backend=self.name,
            backend_version=self.version,
            supported=True,
            success=True,
            message=f"Self-colliding triangle pairs: {count}.",
            elapsed_ms=(perf_counter() - started) * 1000,
            input_hash=input_hash,
            metrics={"self_colliding_pairs": count},
            limitations=self.info().limitations,
        )

    def engineering_offset(
        self,
        mesh: MeshBuffers,
        *,
        distance: float,
        voxel_size: float | None = None,
        sign_mode: str = "Unsigned",
    ) -> GeometryOperationResult:
        started = perf_counter()
        input_hash = mesh.sha256()
        if not _MESHLIB_AVAILABLE:
            return GeometryOperationResult(
                operation="engineering_offset",
                backend=self.name,
                backend_version=self.version,
                supported=False,
                success=False,
                message="meshlib is not available.",
                elapsed_ms=(perf_counter() - started) * 1000,
                input_hash=input_hash,
                limitations=self.info().limitations,
            )
        if distance <= 0:
            return GeometryOperationResult(
                operation="engineering_offset",
                backend=self.name,
                backend_version=self.version,
                supported=True,
                success=False,
                message="Offset distance must be > 0 (technical production parameter).",
                elapsed_ms=(perf_counter() - started) * 1000,
                input_hash=input_hash,
                limitations=self.info().limitations,
            )
        ml = self._to_meshlib(mesh)
        params = mm.OffsetParameters()
        if voxel_size is None:
            voxel_size = float(ml.getBoundingBox().diagonal() * 0.01)
        params.voxelSize = float(voxel_size)
        mode = getattr(mm.SignDetectionMode, sign_mode, mm.SignDetectionMode.Unsigned)
        params.signDetectionMode = mode
        out = mm.offsetMesh(ml, float(distance), params)
        buffers = self._from_meshlib(out)
        return GeometryOperationResult(
            operation="engineering_offset",
            backend=self.name,
            backend_version=self.version,
            supported=True,
            success=len(buffers.vertices) > 0 and len(buffers.faces) > 0,
            message=(
                "Engineering voxel offset produced. "
                "Not manufacturing certified; not clinically approved."
            ),
            elapsed_ms=(perf_counter() - started) * 1000,
            input_hash=input_hash,
            output_hash=buffers.sha256(),
            output_mesh=buffers,
            metrics={
                "distance": distance,
                "voxel_size": voxel_size,
                "sign_mode": sign_mode,
                "output_vertices": len(buffers.vertices),
                "output_faces": len(buffers.faces),
                "parameter_kind": "technical",
            },
            limitations=self.info().limitations,
        )

    def boolean_union_spheres(self) -> GeometryOperationResult:
        started = perf_counter()
        if not _MESHLIB_AVAILABLE:
            return GeometryOperationResult(
                operation="boolean_union",
                backend=self.name,
                backend_version=self.version,
                supported=False,
                success=False,
                message="meshlib is not available.",
                elapsed_ms=(perf_counter() - started) * 1000,
                limitations=self.info().limitations,
            )
        a = mm.makeUVSphere(1.0, 32, 32)
        b = mm.makeUVSphere(1.0, 32, 32)
        b.transform(mm.AffineXf3f.translation(mm.Vector3f(0.7, 0.0, 0.0)))
        result = mm.boolean(a, b, mm.BooleanOperation.Union)
        ok = bool(result.valid()) if callable(result.valid) else bool(result.valid)
        out = self._from_meshlib(result.mesh) if ok else None
        return GeometryOperationResult(
            operation="boolean_union",
            backend=self.name,
            backend_version=self.version,
            supported=True,
            success=ok,
            message="Engineering boolean union (synthetic spheres)."
            if ok
            else f"Boolean failed: {result.errorString}",
            elapsed_ms=(perf_counter() - started) * 1000,
            output_hash=out.sha256() if out else None,
            output_mesh=out,
            metrics={"geometry_kind": "synthetic_engineering"},
            limitations=(
                "Synthetic engineering geometry — not anatomical evidence.",
                *self.info().limitations,
            ),
        )
