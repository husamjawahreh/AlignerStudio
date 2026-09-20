"""Explicit, deterministic engineering demo inputs; never used for real uploaded cases."""

from __future__ import annotations

from domain.case.provenance import DataProvenance
from domain.tooth.segmentation import SegmentationMetadata, ToothInstance, ToothSegmentationResult
from domain.treatment_plan.setup import (
    ToothMovement,
    TreatmentObjective,
    TreatmentObjectiveType,
)


def synthetic_upper_arch() -> ToothSegmentationResult:
    """Return a sixteen-instance geometric fixture for an explicit demo session."""
    instances = []
    for instance_id, lateral in enumerate(range(-15, 16, 2)):
        x = lateral / 2.0
        y = 0.08 * x * x
        vertices = tuple(
            (x + dx, y + dy, dz)
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
                centroid=(x, y, 0.0),
                confidence=1.0,
                provenance=DataProvenance.FIXTURE,
                fixture=True,
                notes="Explicit engineering fixture; not a dental scan.",
            )
        )
    metadata = SegmentationMetadata(
        engine_name="api-engineering-fixture",
        model_name="none",
        model_version="none",
        input_triangle_count=192,
        output_instance_count=16,
        confidence_min=1.0,
        confidence_mean=1.0,
        confidence_max=1.0,
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        notes="Explicit engineering fixture; no segmentation model was used.",
    )
    return ToothSegmentationResult(tuple(instances), metadata, "api-engineering-fixture-upper")


def demo_objectives() -> tuple[TreatmentObjective, ...]:
    return (
        TreatmentObjective(
            "fixture-alignment-11",
            TreatmentObjectiveType.ALIGNMENT,
            "Engineering fixture movement for tooth 11.",
            ((11, ToothMovement(translation_x=0.2)),),
        ),
        TreatmentObjective(
            "fixture-rotation-13",
            TreatmentObjectiveType.ROTATION_CORRECTION,
            "Engineering fixture movement for tooth 13.",
            ((13, ToothMovement(rotation=5.0, tip=1.0, torque=-1.0)),),
        ),
    )
