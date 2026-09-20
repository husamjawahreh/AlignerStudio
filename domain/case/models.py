"""Case domain entity: the top-level orthodontic case being planned."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class CaseStatus(str, Enum):
    """Lifecycle status of a case."""

    CREATED = "created"
    MESH_UPLOADED = "mesh_uploaded"
    MESH_VALIDATED = "mesh_validated"
    MESH_REJECTED = "mesh_rejected"
    PLAN_GENERATED = "plan_generated"


@dataclass(frozen=True)
class MeshAsset:
    """Reference to an uploaded STL mesh file for one arch."""

    arch: str  # "upper" | "lower"
    file_path: str
    original_filename: str
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Case:
    """An orthodontic treatment-planning case for a single patient scan set."""

    id: str = field(default_factory=lambda: str(uuid4()))
    patient_reference: str = ""
    status: CaseStatus = CaseStatus.CREATED
    meshes: list[MeshAsset] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_mesh(self, mesh: MeshAsset) -> None:
        self.meshes = [m for m in self.meshes if m.arch != mesh.arch] + [mesh]
        self.status = CaseStatus.MESH_UPLOADED

    def remove_mesh(self, arch: str) -> MeshAsset | None:
        """Remove one uploaded arch asset and return its former reference."""
        mesh = next((item for item in self.meshes if item.arch == arch), None)
        if mesh is not None:
            self.meshes = [item for item in self.meshes if item.arch != arch]
            self.status = CaseStatus.MESH_UPLOADED if self.meshes else CaseStatus.CREATED
        return mesh

    def mark_validated(self) -> None:
        self.status = CaseStatus.MESH_VALIDATED

    def mark_rejected(self) -> None:
        self.status = CaseStatus.MESH_REJECTED

    def mark_plan_generated(self) -> None:
        self.status = CaseStatus.PLAN_GENERATED
