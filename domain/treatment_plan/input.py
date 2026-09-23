"""Domain-level treatment input derived from reviewed tooth identification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ToothIdentificationResult


class TreatmentPlanningMode(StrEnum):
    CLINICAL_FDI = "clinical_fdi"
    SEMANTIC_ONLY_EXPERIMENTAL = "semantic_only_experimental"


@dataclass(frozen=True)
class TreatmentPlanningInput:
    """The infrastructure-free input contract consumed by treatment planning."""

    identification: ToothIdentificationResult
    provenance: DataProvenance
    fixture: bool
    diagnostics: tuple[str, ...] = ()
    planning_mode: TreatmentPlanningMode = TreatmentPlanningMode.CLINICAL_FDI

    @classmethod
    def from_identification(
        cls,
        identification: ToothIdentificationResult,
        *,
        diagnostics: tuple[str, ...] = (),
        planning_mode: TreatmentPlanningMode = TreatmentPlanningMode.CLINICAL_FDI,
    ) -> TreatmentPlanningInput:
        return cls(
            identification=identification,
            provenance=identification.provenance,
            fixture=identification.fixture,
            diagnostics=diagnostics,
            planning_mode=planning_mode,
        )

    @property
    def ready_for_planning(self) -> bool:
        if self.planning_mode is TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL:
            return bool(self.identification.teeth) and not self.identification.unidentified
        return not self.identification.uncertain and not self.identification.unidentified
