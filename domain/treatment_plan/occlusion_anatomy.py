"""WP-08 occlusion + advanced anatomy treatment-plan binding.

Exposes capability prerequisites to Treatment Setup / Staging without globally
disabling unrelated workflows. Never claims clinical occlusion approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from domain.tooth.advanced_anatomy import AdvancedAnatomyReport
from domain.tooth.occlusion import OcclusionFreshness, OcclusionResult


class OcclusionAnatomyPrerequisite(StrEnum):
    AVAILABLE = "available"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"
    UNAVAILABLE = "unavailable"
    STALE = "stale"


@dataclass(frozen=True)
class OcclusionAnatomyBinding:
    source_input_hash: str | None
    upper_hash: str | None
    lower_hash: str | None
    registration_version_id: str | None
    setup_version_id: str | None
    staging_version_id: str | None


@dataclass(frozen=True)
class OcclusionAnatomyPlan:
    """Downstream-facing capability surface for setup/staging/refinement."""

    binding: OcclusionAnatomyBinding
    freshness: OcclusionFreshness
    occlusion: OcclusionResult | None
    advanced_anatomy: AdvancedAnatomyReport | None
    occlusion_prerequisite: OcclusionAnatomyPrerequisite
    clinical_axes_prerequisite: OcclusionAnatomyPrerequisite
    root_geometry_prerequisite: OcclusionAnatomyPrerequisite
    landmark_prerequisite: OcclusionAnatomyPrerequisite
    notes: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "contract_version": "occlusion_anatomy_binding_1.0",
            "binding": {
                "source_input_hash": self.binding.source_input_hash,
                "upper_hash": self.binding.upper_hash,
                "lower_hash": self.binding.lower_hash,
                "registration_version_id": self.binding.registration_version_id,
                "setup_version_id": self.binding.setup_version_id,
                "staging_version_id": self.binding.staging_version_id,
            },
            "freshness": self.freshness.value,
            "occlusion": self.occlusion.payload() if self.occlusion else None,
            "advanced_anatomy": (
                self.advanced_anatomy.payload() if self.advanced_anatomy else None
            ),
            "prerequisites": {
                "occlusion": self.occlusion_prerequisite.value,
                "clinical_axes": self.clinical_axes_prerequisite.value,
                "root_geometry": self.root_geometry_prerequisite.value,
                "landmarks": self.landmark_prerequisite.value,
            },
            "notes": list(self.notes),
            "clinically_approved": False,
            "occlusion_validated": False,
        }


__all__ = [
    "OcclusionAnatomyBinding",
    "OcclusionAnatomyPlan",
    "OcclusionAnatomyPrerequisite",
]
