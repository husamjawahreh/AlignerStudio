"""Validation ports and basic deterministic geometry checks for Phase 5."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from domain.treatment_plan.setup import TargetToothState, ToothMovement
from domain.treatment_plan.staging import StageToothState


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    message: str
    blocking: bool = False


class MovementLimitValidator(Protocol):
    def validate(self, movement: ToothMovement) -> tuple[ValidationFinding, ...]: ...


class ToothProximityValidator(Protocol):
    def validate(self, states: tuple[TargetToothState, ...]) -> tuple[ValidationFinding, ...]: ...


class CollisionDetector(Protocol):
    def detect(self, states: tuple[TargetToothState, ...]) -> tuple[ValidationFinding, ...]: ...


class AnatomicalConstraintValidator(Protocol):
    def validate(self, states: tuple[TargetToothState, ...]) -> tuple[ValidationFinding, ...]: ...


class StageMovementLimitValidator(Protocol):
    def validate(self, state: StageToothState) -> tuple[ValidationFinding, ...]: ...


class StageCollisionDetector(Protocol):
    def detect(self, states: tuple[StageToothState, ...]) -> tuple[ValidationFinding, ...]: ...


class StageContactValidator(Protocol):
    def validate(self, states: tuple[StageToothState, ...]) -> tuple[ValidationFinding, ...]: ...


class StageClinicalConstraintValidator(Protocol):
    def validate(self, states: tuple[StageToothState, ...]) -> tuple[ValidationFinding, ...]: ...


class BasicGeometryValidator:
    """Checks finite target geometry only; no clinical threshold is applied."""

    def validate(self, states: tuple[TargetToothState, ...]) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        for state in states:
            target = np.asarray(state.target_vertices, dtype=np.float64)
            if target.size == 0 or target.ndim != 2 or target.shape[1] != 3:
                findings.append(
                    ValidationFinding(
                        "malformed_target_geometry",
                        f"Tooth {state.tooth_number} has malformed target vertices.",
                        blocking=True,
                    )
                )
            elif not np.all(np.isfinite(target)):
                findings.append(
                    ValidationFinding(
                        "non_finite_target_geometry",
                        f"Tooth {state.tooth_number} has non-finite target vertices.",
                        blocking=True,
                    )
                )
        return tuple(findings)
