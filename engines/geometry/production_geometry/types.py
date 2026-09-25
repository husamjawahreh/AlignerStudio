"""Neutral mesh buffers and operation results for Production CAD backends."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MeshBuffers:
    """Library-agnostic triangle mesh (vertices Nx3, faces Mx3)."""

    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]
    identity: str = ""

    def sha256(self) -> str:
        digest = hashlib.sha256()
        for point in self.vertices:
            digest.update(f"{float(point[0]):.9f},{float(point[1]):.9f},{float(point[2]):.9f};".encode())
        for face in self.faces:
            digest.update(f"{int(face[0])},{int(face[1])},{int(face[2])};".encode())
        return digest.hexdigest()


@dataclass(frozen=True)
class GeometryBackendInfo:
    name: str
    version: str | None
    available: bool
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeometryOperationResult:
    operation: str
    backend: str
    backend_version: str | None
    supported: bool
    success: bool
    message: str
    elapsed_ms: float
    input_hash: str | None = None
    output_hash: str | None = None
    output_mesh: MeshBuffers | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    provenance: str = "experimental"
    manufacturing_certified: bool = False
    clinically_approved: bool = False

    def payload(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "backend": self.backend,
            "backend_version": self.backend_version,
            "supported": self.supported,
            "success": self.success,
            "message": self.message,
            "elapsed_ms": self.elapsed_ms,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "metrics": dict(self.metrics),
            "limitations": list(self.limitations),
            "provenance": self.provenance,
            "manufacturing_certified": False,
            "clinically_approved": False,
            "has_output_mesh": self.output_mesh is not None,
        }
