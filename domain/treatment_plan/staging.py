"""Phase 6 treatment staging domain models."""

from __future__ import annotations

from dataclasses import dataclass

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ToothCoordinateSystem, Vector3
from domain.treatment_plan.setup import ToothMovement


@dataclass(frozen=True)
class StageMovement:
    """Movement applied to one tooth at one deterministic stage."""

    tooth_number: int | str
    movement: ToothMovement
    progress: float


@dataclass(frozen=True)
class StageToothState:
    """One tooth scene state at a stage, retaining source and final relationship."""

    tooth_number: int | str | None
    source_instance_id: int
    source_vertices: tuple[Vector3, ...]
    source_faces: tuple[tuple[int, int, int], ...]
    final_target_vertices: tuple[Vector3, ...]
    final_target_faces: tuple[tuple[int, int, int], ...]
    vertices: tuple[Vector3, ...]
    coordinate_system: ToothCoordinateSystem
    movement: StageMovement
    provenance: DataProvenance
    fixture: bool
    notes: str = ""
    tooth_ref: str | None = None
    semantic_label: int | None = None
    arch: str | None = None
    planning_mode: str = "clinical_fdi"


@dataclass(frozen=True)
class TreatmentStage:
    """An immutable, ordered state of the proposed treatment setup."""

    stage_index: int
    stage_id: str
    tooth_states: tuple[StageToothState, ...]
    provenance: DataProvenance
    fixture: bool
    stage_hash: str
    notes: str = ""


@dataclass(frozen=True)
class StagingConfiguration:
    """Explicit staging controls; values are engineering interpolation settings."""

    stage_count: int = 2
    engine_version: str = "phase6-staging-1"

    def __post_init__(self) -> None:
        if self.stage_count < 2:
            raise ValueError("stage_count must include Stage 0 and a distinct final stage")
        if not self.engine_version.strip():
            raise ValueError("engine_version must not be empty")


@dataclass(frozen=True)
class StagingResult:
    """Deterministic stages for one Phase 5 proposal."""

    plan_id: str
    staging_id: str
    stages: tuple[TreatmentStage, ...]
    provenance: DataProvenance
    fixture: bool
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]

    @property
    def final_stage(self) -> TreatmentStage:
        return self.stages[-1]

    @property
    def stage_count(self) -> int:
        return len(self.stages)


__all__ = [
    "StageMovement",
    "StageToothState",
    "StagingConfiguration",
    "StagingResult",
    "TreatmentStage",
]
