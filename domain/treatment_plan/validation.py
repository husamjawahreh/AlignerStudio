"""Purely geometric validation result models for staged treatment plans."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.case.provenance import DataProvenance


class ValidationStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    ERROR = "error"
    INVALID = "invalid"


@dataclass(frozen=True)
class ProximityResult:
    stage_index: int
    tooth_a: int | str
    tooth_b: int | str
    measured_distance: float
    threshold: float
    status: ValidationStatus
    provenance: DataProvenance
    result_id: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class CollisionResult:
    stage_index: int
    tooth_a: int | str
    tooth_b: int | str
    intersects: bool
    measured_depth: float | None
    tolerance: float
    status: ValidationStatus
    provenance: DataProvenance
    result_id: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContactResult:
    stage_index: int
    tooth_a: int | str
    tooth_b: int | str
    is_contact: bool
    measured_distance: float
    tolerance: float
    status: ValidationStatus
    provenance: DataProvenance
    result_id: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToothValidationResult:
    stage_index: int
    tooth_number: int | str
    proximity_results: tuple[ProximityResult, ...]
    collision_results: tuple[CollisionResult, ...]
    contact_results: tuple[ContactResult, ...]
    status: ValidationStatus
    provenance: DataProvenance
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class StageValidationResult:
    stage_index: int
    stage_id: str
    tooth_results: tuple[ToothValidationResult, ...]
    proximity_results: tuple[ProximityResult, ...]
    collision_results: tuple[CollisionResult, ...]
    contact_results: tuple[ContactResult, ...]
    status: ValidationStatus
    provenance: DataProvenance
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class TreatmentValidationReport:
    plan_id: str
    report_id: str
    stage_results: tuple[StageValidationResult, ...]
    status: ValidationStatus
    provenance: DataProvenance
    fixture: bool
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


__all__ = [
    "CollisionResult",
    "ContactResult",
    "ProximityResult",
    "StageValidationResult",
    "ToothValidationResult",
    "TreatmentValidationReport",
    "ValidationStatus",
]
