"""Treatment plan domain entities: a plan is an ordered list of stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from domain.case.provenance import DataProvenance
from domain.tooth.models import Tooth


@dataclass(frozen=True)
class ToothPosition:
    """Placeholder position of a tooth at a given stage.

    Phase 1 only records the tooth identity; real transforms (translation +
    rotation vs. a reference frame) belong to a later phase once
    ``engines/arrangement`` exists.
    """

    tooth: Tooth


@dataclass(frozen=True)
class Stage:
    """A single step of the treatment plan (e.g. one aligner)."""

    index: int
    tooth_positions: tuple[ToothPosition, ...]
    provenance: DataProvenance
    fixture: bool = False
    notes: str = ""


@dataclass
class TreatmentPlan:
    """An ordered sequence of stages produced for a case."""

    id: str = field(default_factory=lambda: str(uuid4()))
    case_id: str = ""
    stages: tuple[Stage, ...] = field(default_factory=tuple)
    provenance: DataProvenance = DataProvenance.GENERATED
    fixture: bool = False
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def stage_count(self) -> int:
        return len(self.stages)
