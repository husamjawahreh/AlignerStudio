"""Geometry-only tooth segmentation domain models.

Segmentation deliberately does not identify teeth. FDI assignment belongs to a
separate future identification stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.case.provenance import DataProvenance


@dataclass(frozen=True)
class ToothInstance:
    """One deterministic connected segment produced by a segmentation model."""

    instance_id: int
    triangle_indices: tuple[int, ...]
    vertex_indices: tuple[int, ...]
    mesh_vertices: tuple[tuple[float, float, float], ...]
    mesh_faces: tuple[tuple[int, int, int], ...]
    centroid: tuple[float, float, float]
    confidence: float
    provenance: DataProvenance
    fixture: bool = False
    notes: str = ""


@dataclass(frozen=True)
class SegmentationMetadata:
    """Traceability and quality metadata for one segmentation run."""

    engine_name: str
    model_name: str
    model_version: str
    input_triangle_count: int
    output_instance_count: int
    confidence_min: float
    confidence_mean: float
    confidence_max: float
    provenance: DataProvenance
    fixture: bool = False
    notes: str = ""


@dataclass(frozen=True)
class ToothSegmentationResult:
    """Geometry-only segmentation output plus its provenance metadata."""

    instances: tuple[ToothInstance, ...]
    metadata: SegmentationMetadata
    source_mesh_path: str = field(compare=False)

    def __post_init__(self) -> None:
        expected_ids = tuple(range(len(self.instances)))
        actual_ids = tuple(instance.instance_id for instance in self.instances)
        if actual_ids != expected_ids:
            raise ValueError("Segmentation instances must have contiguous deterministic IDs")
        if self.metadata.output_instance_count != len(self.instances):
            raise ValueError("Segmentation metadata instance count does not match instances")
