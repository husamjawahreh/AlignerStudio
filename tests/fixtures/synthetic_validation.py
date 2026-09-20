"""Deterministic cuboid mesh fixtures for geometric validation only."""

from __future__ import annotations

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ToothCoordinateSystem
from domain.treatment_plan.setup import ToothMovement
from domain.treatment_plan.staging import (
    StageMovement,
    StageToothState,
    StagingResult,
    TreatmentStage,
)

AXES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
FACES = (
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


def cuboid_vertices(origin: tuple[float, float, float], size: float = 1.0):
    x, y, z = origin
    return tuple(
        (x + dx * size, y + dy * size, z + dz * size)
        for dx, dy, dz in (
            (0, 0, 0),
            (1, 0, 0),
            (1, 1, 0),
            (0, 1, 0),
            (0, 0, 1),
            (1, 0, 1),
            (1, 1, 1),
            (0, 1, 1),
        )
    )


def validation_stage(origins: tuple[tuple[float, float, float], ...]) -> TreatmentStage:
    states = []
    frame = ToothCoordinateSystem((0.0, 0.0, 0.0), *AXES)
    for index, origin in enumerate(origins, start=11):
        vertices = cuboid_vertices(origin)
        states.append(
            StageToothState(
                tooth_number=index,
                source_instance_id=index,
                source_vertices=vertices,
                source_faces=FACES,
                final_target_vertices=vertices,
                final_target_faces=FACES,
                vertices=vertices,
                coordinate_system=frame,
                movement=StageMovement(index, ToothMovement(), 0.0),
                provenance=DataProvenance.FIXTURE,
                fixture=True,
                notes="Validation fixture only.",
            )
        )
    return TreatmentStage(
        stage_index=0,
        stage_id="fixture-stage-0",
        tooth_states=tuple(states),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        stage_hash="fixture-stage-hash",
    )


def validation_result(stage: TreatmentStage) -> StagingResult:
    return StagingResult(
        plan_id="fixture-validation-plan",
        staging_id="fixture-validation-staging",
        stages=(stage,),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        assumptions=("Synthetic geometry fixture only.",),
        warnings=(),
        limitations=(),
    )
