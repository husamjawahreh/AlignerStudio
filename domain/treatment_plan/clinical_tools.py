"""WP-07 clinical tools contracts — IPR / attachments honesty layer.

Wraps Phase-10 adjunct proposals with truth states, freshness, and
measured/proposed/doctor-entered distinction. Never invents clinical prescriptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ClinicalToolTruthState(StrEnum):
    VERIFIED = "verified"
    COMPUTED = "computed"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"


class ClinicalToolFreshness(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class ClinicalToolValueSource(StrEnum):
    MEASURED = "measured"
    COMPUTED_PROPOSAL = "computed_proposal"
    DOCTOR_ENTERED = "doctor_entered"
    NOT_AVAILABLE = "not_available"


class ClinicalCapabilityState(StrEnum):
    AVAILABLE = "available"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ClinicalToolsReadiness:
    ipr_measurement: ClinicalCapabilityState
    ipr_proposal: ClinicalCapabilityState
    attachment_placement: ClinicalCapabilityState
    attachment_geometry: ClinicalCapabilityState
    validation: ClinicalCapabilityState
    setup_binding: ClinicalToolFreshness
    staging_binding: ClinicalToolFreshness
    doctor_review_required: bool
    source_geometry: ClinicalCapabilityState
    notes: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "ipr_measurement": self.ipr_measurement.value,
            "ipr_proposal": self.ipr_proposal.value,
            "attachment_placement": self.attachment_placement.value,
            "attachment_geometry": self.attachment_geometry.value,
            "validation": self.validation.value,
            "setup_binding": self.setup_binding.value,
            "staging_binding": self.staging_binding.value,
            "doctor_review_required": self.doctor_review_required,
            "source_geometry": self.source_geometry.value,
            "notes": list(self.notes),
            "clinically_approved": False,
        }


def evaluate_clinical_freshness(
    *,
    bound_setup_version_id: str | None,
    current_setup_version_id: str | None,
    bound_staging_version_id: str | None,
    current_staging_version_id: str | None,
    has_tools: bool,
) -> tuple[ClinicalToolFreshness, ClinicalToolFreshness, ClinicalToolFreshness]:
    """Return (overall, setup_binding, staging_binding)."""
    if not has_tools:
        return (
            ClinicalToolFreshness.UNAVAILABLE,
            ClinicalToolFreshness.UNAVAILABLE,
            ClinicalToolFreshness.UNAVAILABLE,
        )
    setup = ClinicalToolFreshness.UNAVAILABLE
    if bound_setup_version_id and current_setup_version_id:
        setup = (
            ClinicalToolFreshness.CURRENT
            if bound_setup_version_id == current_setup_version_id
            else ClinicalToolFreshness.STALE
        )
    staging = ClinicalToolFreshness.UNAVAILABLE
    if bound_staging_version_id and current_staging_version_id:
        staging = (
            ClinicalToolFreshness.CURRENT
            if bound_staging_version_id == current_staging_version_id
            else ClinicalToolFreshness.STALE
        )
    elif bound_staging_version_id is None and current_staging_version_id is None:
        staging = ClinicalToolFreshness.CURRENT
    overall = ClinicalToolFreshness.CURRENT
    if setup is ClinicalToolFreshness.STALE or staging is ClinicalToolFreshness.STALE:
        overall = ClinicalToolFreshness.STALE
    if setup is ClinicalToolFreshness.UNAVAILABLE and staging is ClinicalToolFreshness.UNAVAILABLE:
        overall = ClinicalToolFreshness.UNAVAILABLE
    return overall, setup, staging


__all__ = [
    "ClinicalCapabilityState",
    "ClinicalToolFreshness",
    "ClinicalToolTruthState",
    "ClinicalToolValueSource",
    "ClinicalToolsReadiness",
    "evaluate_clinical_freshness",
]
