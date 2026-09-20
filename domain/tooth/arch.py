"""Descriptive arch-analysis domain models."""

from __future__ import annotations

from dataclasses import dataclass

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ArchType, Vector3


@dataclass(frozen=True)
class ArchCenterlinePoint:
    instance_id: int
    point: Vector3


@dataclass(frozen=True)
class ArchMeasurements:
    """Geometry measurements; these are not diagnoses or clinical thresholds."""

    arch: ArchType
    centerline: tuple[ArchCenterlinePoint, ...]
    ordered_instance_ids: tuple[int, ...]
    total_width: float
    left_half_width: float
    right_half_width: float
    anterior_width: float | None
    posterior_width: float | None
    consecutive_tooth_distances: tuple[float, ...]
    anterior_to_posterior_order: tuple[int, ...]
    provenance: DataProvenance
    fixture: bool
    notes: str = ""
