"""Data-quality report for anatomical intelligence (honest gap reporting)."""

from __future__ import annotations

from dataclasses import dataclass

from domain.case.provenance import DataProvenance
from domain.tooth.anatomy_extent import AnatomyExtent


@dataclass(frozen=True)
class DataQualityReport:
    """Structured data-quality state derived from existing evidence only."""

    scale_validation: str
    units: str
    mesh_quality: str
    incomplete_scans: bool
    missing_teeth: bool
    ambiguous_identity: bool
    incomplete_occlusion: bool
    missing_anatomy: bool
    anatomy_extent: AnatomyExtent
    findings: tuple[str, ...]
    provenance: DataProvenance
    fixture: bool = False
    requires_review: bool = True

    def payload(self) -> dict:
        return {
            "scale_validation": self.scale_validation,
            "units": self.units,
            "mesh_quality": self.mesh_quality,
            "incomplete_scans": self.incomplete_scans,
            "missing_teeth": self.missing_teeth,
            "ambiguous_identity": self.ambiguous_identity,
            "incomplete_occlusion": self.incomplete_occlusion,
            "missing_anatomy": self.missing_anatomy,
            "anatomy_extent": self.anatomy_extent.value,
            "findings": list(self.findings),
            "provenance": self.provenance.value,
            "fixture": self.fixture,
            "requires_review": self.requires_review,
        }
