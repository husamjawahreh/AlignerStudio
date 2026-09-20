"""Deterministic engineering-only upper/lower arch fixture."""

from __future__ import annotations

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ArchType
from domain.tooth.segmentation import SegmentationMetadata, ToothInstance, ToothSegmentationResult


def build_synthetic_arch(arch: ArchType) -> ToothSegmentationResult:
    """Build sixteen disconnected cuboids arranged on a simple arch curve."""
    instances = []
    for instance_id, lateral in enumerate(range(-15, 16, 2)):
        x = lateral / 2.0
        y = (0.08 if arch is ArchType.UPPER else -0.08) * x * x
        z = 0.0
        vertices = tuple(
            (x + dx, y + dy, z + dz)
            for dx, dy, dz in (
                (-0.15, -0.15, -0.2),
                (0.15, -0.15, -0.2),
                (0.15, 0.15, -0.2),
                (-0.15, 0.15, -0.2),
                (-0.15, -0.15, 0.2),
                (0.15, -0.15, 0.2),
                (0.15, 0.15, 0.2),
                (-0.15, 0.15, 0.2),
            )
        )
        faces = (
            (0, 1, 2),
            (0, 2, 3),
            (4, 6, 5),
            (4, 7, 6),
            (0, 4, 5),
            (0, 5, 1),
            (1, 5, 6),
            (1, 6, 2),
            (2, 6, 7),
            (2, 7, 3),
            (3, 7, 4),
            (3, 4, 0),
        )
        instances.append(
            ToothInstance(
                instance_id=instance_id,
                triangle_indices=tuple(range(instance_id * 12, instance_id * 12 + 12)),
                vertex_indices=tuple(range(8)),
                mesh_vertices=vertices,
                mesh_faces=faces,
                centroid=(x, y, z),
                confidence=1.0,
                provenance=DataProvenance.FIXTURE,
                fixture=True,
                notes="Synthetic geometry fixture only.",
            )
        )
    metadata = SegmentationMetadata(
        engine_name="synthetic-fixture",
        model_name="synthetic-fixture",
        model_version="1",
        input_triangle_count=192,
        output_instance_count=16,
        confidence_min=1.0,
        confidence_mean=1.0,
        confidence_max=1.0,
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        notes="Engineering fixture; not a dental scan.",
    )
    return ToothSegmentationResult(tuple(instances), metadata, f"synthetic-{arch.value}-arch")
