"""Domain-level treatment input derived from reviewed tooth identification."""

from __future__ import annotations

from dataclasses import dataclass

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ToothIdentificationResult


@dataclass(frozen=True)
class TreatmentPlanningInput:
    """The infrastructure-free input contract consumed by treatment planning."""

    identification: ToothIdentificationResult
    provenance: DataProvenance
    fixture: bool
    diagnostics: tuple[str, ...] = ()

    @classmethod
    def from_identification(
        cls,
        identification: ToothIdentificationResult,
        *,
        diagnostics: tuple[str, ...] = (),
    ) -> TreatmentPlanningInput:
        return cls(
            identification=identification,
            provenance=identification.provenance,
            fixture=identification.fixture,
            diagnostics=diagnostics,
        )

    @property
    def ready_for_planning(self) -> bool:
        return not self.identification.uncertain and not self.identification.unidentified
