"""WP-08 advanced anatomy capability model — honesty over fabrication.

Distinguishes crown / root / landmark / clinical-axis / generic geometric /
CBCT volumetric capabilities. Never fabricates anatomy the source does not contain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from domain.case.provenance import DataProvenance
from domain.tooth.anatomy_extent import AnatomyExtent


ADVANCED_ANATOMY_CONTRACT_VERSION = "advanced_anatomy_1.0"


class AnatomyCapabilityKind(StrEnum):
    CROWN_GEOMETRY = "crown_geometry"
    ROOT_GEOMETRY = "root_geometry"
    LANDMARK_GEOMETRY = "landmark_geometry"
    CLINICAL_AXES = "clinical_axes"
    GENERIC_GEOMETRIC_AXES = "generic_geometric_axes"
    CBCT_VOLUMETRIC_ANATOMY = "cbct_volumetric_anatomy"


class AnatomyTruthState(StrEnum):
    VERIFIED = "verified"
    COMPUTED = "computed"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"


@dataclass(frozen=True)
class AnatomyCapability:
    """One anatomy capability with explicit truth, source, and provenance."""

    kind: AnatomyCapabilityKind
    truth_state: AnatomyTruthState
    source: str | None
    source_artifact: str | None
    source_hash: str | None
    algorithm: str | None
    algorithm_version: str | None
    generated_at: str | None
    limitations: tuple[str, ...]
    provenance: DataProvenance
    clinical: bool
    notes: tuple[str, ...] = ()
    value: dict[str, Any] | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "truth_state": self.truth_state.value,
            "source": self.source,
            "source_artifact": self.source_artifact,
            "source_hash": self.source_hash,
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "generated_at": self.generated_at,
            "limitations": list(self.limitations),
            "provenance": self.provenance.value,
            "clinical": self.clinical,
            "notes": list(self.notes),
            "value": self.value,
        }


@dataclass(frozen=True)
class AdvancedAnatomyReport:
    """Case-level advanced anatomy capability document."""

    contract_version: str
    case_id: str
    anatomy_extent: AnatomyExtent
    capabilities: tuple[AnatomyCapability, ...]
    crown_geometry: AnatomyTruthState
    root_geometry: AnatomyTruthState
    landmark_geometry: AnatomyTruthState
    clinical_axes: AnatomyTruthState
    generic_geometric_axes: AnatomyTruthState
    cbct_volumetric_anatomy: AnatomyTruthState
    generated_at: str
    provenance: DataProvenance
    fixture: bool
    limitations: tuple[str, ...]
    timings_ms: dict[str, float | None] = field(default_factory=dict)
    source_artifact_hashes: dict[str, str | None] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "case_id": self.case_id,
            "anatomy_extent": self.anatomy_extent.value,
            "capabilities": [item.payload() for item in self.capabilities],
            "crown_geometry": self.crown_geometry.value,
            "root_geometry": self.root_geometry.value,
            "landmark_geometry": self.landmark_geometry.value,
            "clinical_axes": self.clinical_axes.value,
            "generic_geometric_axes": self.generic_geometric_axes.value,
            "cbct_volumetric_anatomy": self.cbct_volumetric_anatomy.value,
            "generated_at": self.generated_at,
            "provenance": self.provenance.value,
            "fixture": self.fixture,
            "limitations": list(self.limitations),
            "timings_ms": dict(self.timings_ms),
            "source_artifact_hashes": dict(self.source_artifact_hashes),
            "clinically_approved": False,
        }


def not_available_capability(
    kind: AnatomyCapabilityKind,
    *,
    reason: str,
    provenance: DataProvenance,
    clinical: bool,
    source_artifact: str | None = None,
    source_hash: str | None = None,
    generated_at: str | None = None,
) -> AnatomyCapability:
    return AnatomyCapability(
        kind=kind,
        truth_state=AnatomyTruthState.NOT_AVAILABLE,
        source=None,
        source_artifact=source_artifact,
        source_hash=source_hash,
        algorithm=None,
        algorithm_version=None,
        generated_at=generated_at,
        limitations=(reason,),
        provenance=provenance,
        clinical=clinical,
        notes=(reason,),
        value=None,
    )


__all__ = [
    "ADVANCED_ANATOMY_CONTRACT_VERSION",
    "AdvancedAnatomyReport",
    "AnatomyCapability",
    "AnatomyCapabilityKind",
    "AnatomyTruthState",
    "not_available_capability",
]
