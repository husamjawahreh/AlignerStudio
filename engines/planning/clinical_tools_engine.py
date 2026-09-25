"""WP-07 clinical tools engine — honesty/view layer over Phase-10 proposals.

Does not invent IPR amounts, attachment prescriptions, enamel limits, or clinical approval.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from domain.treatment_plan.clinical_tools import (
    ClinicalCapabilityState,
    ClinicalToolFreshness,
    ClinicalToolTruthState,
    ClinicalToolValueSource,
    ClinicalToolsReadiness,
    evaluate_clinical_freshness,
)
from domain.treatment_plan.proposals import (
    AttachmentSite,
    IPRSite,
    ProposalStatus,
    TreatmentProposalResult,
)


@dataclass(frozen=True)
class ClinicalToolsBinding:
    source_setup_version_id: str
    source_staging_version_id: str | None
    adjuncts_proposal_id: str


@dataclass(frozen=True)
class ClinicalToolsPlan:
    binding: ClinicalToolsBinding
    freshness: ClinicalToolFreshness
    readiness: ClinicalToolsReadiness
    ipr_site_count: int
    attachment_site_count: int
    measurable_ipr_pairs: int
    unavailable_ipr_pairs: int
    limitations: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "contract_version": "clinical_tools_1.0",
            "source_setup_version_id": self.binding.source_setup_version_id,
            "source_staging_version_id": self.binding.source_staging_version_id,
            "adjuncts_proposal_id": self.binding.adjuncts_proposal_id,
            "freshness": self.freshness.value,
            "readiness": self.readiness.payload(),
            "ipr_site_count": self.ipr_site_count,
            "attachment_site_count": self.attachment_site_count,
            "measurable_ipr_pairs": self.measurable_ipr_pairs,
            "unavailable_ipr_pairs": self.unavailable_ipr_pairs,
            "limitations": list(self.limitations),
            "clinically_approved": False,
            "notes": [
                "Centroid-distance space deltas are geometric COMPUTED values, not clinical IPR prescriptions.",
                "Attachment candidates without dimensions are not clinical prescriptions.",
                "Empty site lists do not prove that IPR or attachments are unnecessary.",
                "WP-10 and later packages are not started.",
            ],
        }


def ipr_truth_state(site: IPRSite) -> ClinicalToolTruthState:
    if site.status is ProposalStatus.UNABLE_TO_DETERMINE:
        return ClinicalToolTruthState.NOT_AVAILABLE
    if site.current_measurement.value is None:
        return ClinicalToolTruthState.NOT_AVAILABLE
    # Geometric computation exists — never VERIFIED from generation alone.
    if site.status in (
        ProposalStatus.NEEDS_REVIEW,
        ProposalStatus.GENERATED,
        ProposalStatus.DOCTOR_MODIFIED,
        ProposalStatus.ACCEPTED,
        ProposalStatus.REJECTED,
    ):
        return ClinicalToolTruthState.REQUIRES_REVIEW
    return ClinicalToolTruthState.COMPUTED


def attachment_truth_state(site: AttachmentSite) -> ClinicalToolTruthState:
    if site.dimensions is None or not site.generated:
        return ClinicalToolTruthState.REQUIRES_REVIEW
    return ClinicalToolTruthState.REQUIRES_REVIEW


def ipr_value_source(site: IPRSite) -> ClinicalToolValueSource:
    if site.doctor_entered_amount is not None or site.status is ProposalStatus.DOCTOR_MODIFIED:
        return ClinicalToolValueSource.DOCTOR_ENTERED
    if site.proposed_amount is not None and site.current_measurement.value is not None:
        return ClinicalToolValueSource.COMPUTED_PROPOSAL
    if site.current_measurement.value is not None:
        return ClinicalToolValueSource.MEASURED
    return ClinicalToolValueSource.NOT_AVAILABLE


def serialize_ipr_site(site: IPRSite, *, display_stage: int | None) -> dict[str, Any]:
    truth = ipr_truth_state(site)
    source = ipr_value_source(site)
    unit = site.current_measurement.unit or "model units"
    measured = site.current_measurement.value
    computed_proposal = site.required_space
    doctor_entered = site.doctor_entered_amount
    # Active amount for editing UI — doctor-entered wins when present.
    active = (
        doctor_entered
        if doctor_entered is not None
        else site.proposed_amount
    )
    return {
        "siteId": site.site_id,
        "toothA": site.tooth_a,
        "toothB": site.tooth_b,
        "toothRefA": site.tooth_a if isinstance(site.tooth_a, str) else None,
        "toothRefB": site.tooth_b if isinstance(site.tooth_b, str) else None,
        "currentDistance": measured,
        "targetDistance": site.target_measurement.value,
        "measuredAmount": measured,
        "computedProposalAmount": computed_proposal,
        "doctorEnteredAmount": doctor_entered,
        "proposedAmount": active,
        "amountUnit": unit,
        "measurementMethod": site.current_measurement.method,
        "valueSource": source.value,
        "truthState": truth.value,
        "status": site.status.value,
        "warning": "; ".join(warning.message for warning in site.warnings),
        "fixture": site.fixture,
        "stage": site.stage_index if site.stage_index is not None else display_stage,
        "displayStageHint": display_stage,
        "clinicallyApproved": False,
        "limitations": [
            "Geometric centroid distance is not a clinical IPR recommendation.",
            "No enamel safety threshold was applied.",
            f"Unit is '{unit}' — not claimed as millimetres unless explicitly calibrated.",
        ],
    }


def serialize_attachment_site(site: AttachmentSite, *, display_stage: int | None) -> dict[str, Any]:
    truth = attachment_truth_state(site)
    return {
        "siteId": site.site_id,
        "toothNumber": site.tooth_number,
        "toothRef": site.tooth_number if isinstance(site.tooth_number, str) else None,
        "attachmentType": site.attachment_type.value,
        "referencePoint": site.reference_point,
        "reason": site.reason,
        "status": site.status.value,
        "warning": "; ".join(warning.message for warning in site.warnings),
        "fixture": site.fixture,
        "dimensions": site.dimensions,
        "stage": site.stage_index if site.stage_index is not None else display_stage,
        "displayStageHint": display_stage,
        "generated": site.generated,
        "truthState": truth.value,
        "geometryAvailable": site.dimensions is not None,
        "clinicallyApproved": False,
        "limitations": [
            "Attachment type/dimensions are domain representations, not clinical prescriptions.",
            "Placement without verified clinical axes requires review.",
            "Manufacturing booleaning is out of scope (WP-10).",
        ],
    }


def build_clinical_tools_plan(
    adjuncts: TreatmentProposalResult | None,
    *,
    current_setup_version_id: str,
    current_staging_version_id: str | None,
    bound_setup_version_id: str | None,
    bound_staging_version_id: str | None,
    has_validation: bool,
    has_source_geometry: bool,
) -> ClinicalToolsPlan:
    has_tools = adjuncts is not None
    overall, setup_binding, staging_binding = evaluate_clinical_freshness(
        bound_setup_version_id=bound_setup_version_id or (adjuncts.version_id if adjuncts else None),
        current_setup_version_id=current_setup_version_id,
        bound_staging_version_id=bound_staging_version_id,
        current_staging_version_id=current_staging_version_id,
        has_tools=has_tools,
    )
    ipr_sites = adjuncts.ipr.sites if adjuncts else ()
    att_sites = adjuncts.attachments.sites if adjuncts else ()
    measurable = sum(
        1 for site in ipr_sites if site.current_measurement.value is not None
    )
    unavailable = sum(
        1
        for site in ipr_sites
        if site.status is ProposalStatus.UNABLE_TO_DETERMINE
        or site.current_measurement.value is None
    )
    limitations = [
        "IPR proposals use centroid-distance space deltas (Phase-10 method), not contact/proximity enamel reduction.",
        "Attachment candidates without generated geometry are review-only placeholders.",
        "No biological enamel or attachment clinical thresholds were invented.",
    ]
    if overall is ClinicalToolFreshness.STALE:
        limitations.append(
            "Clinical tools are stale relative to the current Treatment Setup and/or Smart Staging version."
        )
    readiness = ClinicalToolsReadiness(
        ipr_measurement=(
            ClinicalCapabilityState.REQUIRES_REVIEW
            if measurable > 0
            else ClinicalCapabilityState.NOT_AVAILABLE
        ),
        ipr_proposal=(
            ClinicalCapabilityState.REQUIRES_REVIEW
            if any(site.proposed_amount is not None for site in ipr_sites)
            else ClinicalCapabilityState.NOT_AVAILABLE
        ),
        attachment_placement=(
            ClinicalCapabilityState.REQUIRES_REVIEW
            if att_sites
            else ClinicalCapabilityState.NOT_AVAILABLE
        ),
        attachment_geometry=(
            ClinicalCapabilityState.AVAILABLE
            if any(site.dimensions is not None for site in att_sites)
            else ClinicalCapabilityState.NOT_AVAILABLE
        ),
        validation=(
            ClinicalCapabilityState.AVAILABLE
            if has_validation
            else ClinicalCapabilityState.UNAVAILABLE
        ),
        setup_binding=setup_binding,
        staging_binding=staging_binding,
        doctor_review_required=True,
        source_geometry=(
            ClinicalCapabilityState.AVAILABLE
            if has_source_geometry
            else ClinicalCapabilityState.NOT_AVAILABLE
        ),
        notes=(
            "Capability gates are not an AI score.",
            "Doctor review is mandatory for clinically meaningful IPR/attachment decisions.",
        ),
    )
    binding = ClinicalToolsBinding(
        source_setup_version_id=bound_setup_version_id
        or (adjuncts.version_id if adjuncts else current_setup_version_id),
        source_staging_version_id=bound_staging_version_id,
        adjuncts_proposal_id=adjuncts.proposal_id if adjuncts else "",
    )
    return ClinicalToolsPlan(
        binding=binding,
        freshness=overall,
        readiness=readiness,
        ipr_site_count=len(ipr_sites),
        attachment_site_count=len(att_sites),
        measurable_ipr_pairs=measurable,
        unavailable_ipr_pairs=unavailable,
        limitations=tuple(limitations),
    )


def preserve_doctor_ipr_amounts(
    previous: TreatmentProposalResult | None,
    generated: TreatmentProposalResult,
) -> TreatmentProposalResult:
    """Keep doctor-entered IPR amounts across regeneration (do not silent overwrite)."""
    if previous is None:
        return generated
    prior = {
        site.site_id: site
        for site in previous.ipr.sites
        if site.doctor_entered_amount is not None
        or site.status is ProposalStatus.DOCTOR_MODIFIED
    }
    if not prior:
        return generated
    updated_sites = []
    for site in generated.ipr.sites:
        old = prior.get(site.site_id)
        if old is None:
            updated_sites.append(site)
            continue
        amount = old.doctor_entered_amount
        if amount is None and old.status is ProposalStatus.DOCTOR_MODIFIED:
            amount = old.proposed_amount
        updated_sites.append(
            replace(
                site,
                doctor_entered_amount=amount,
                proposed_amount=amount if amount is not None else site.proposed_amount,
                status=ProposalStatus.DOCTOR_MODIFIED
                if amount is not None
                else site.status,
            )
        )
    ipr = replace(generated.ipr, sites=tuple(updated_sites))
    return replace(generated, ipr=ipr)


__all__ = [
    "ClinicalToolsBinding",
    "ClinicalToolsPlan",
    "attachment_truth_state",
    "build_clinical_tools_plan",
    "ipr_truth_state",
    "ipr_value_source",
    "preserve_doctor_ipr_amounts",
    "serialize_attachment_site",
    "serialize_ipr_site",
]
