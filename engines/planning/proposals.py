"""Deterministic geometry/objective-driven adjunct proposal engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace

import numpy as np

from domain.case.provenance import DataProvenance
from domain.treatment_plan.proposals import (
    AttachmentProposal,
    AttachmentSite,
    AttachmentType,
    IPRMeasurement,
    IPRProposal,
    IPRSite,
    ProposalStatus,
    ProposalWarning,
    TreatmentProposalResult,
)
from domain.treatment_plan.setup import TreatmentPlanProposal


class TreatmentProposalError(ValueError):
    """Raised when an adjunct proposal cannot be safely changed."""


@dataclass(frozen=True)
class TreatmentProposalEngine:
    """Generates review-only IPR and attachment proposals from plan geometry."""

    engine_version: str = "phase10-proposals-1"

    def generate(
        self,
        plan: TreatmentPlanProposal,
        previous: TreatmentProposalResult | None = None,
    ) -> TreatmentProposalResult:
        if plan.setup is None:
            warning = ProposalWarning(
                "missing_setup",
                "Target setup is unavailable; adjunct proposals cannot be determined.",
            )
            return self._empty_result(plan, warning, previous)
        source = {self._state_key(state): state for state in plan.setup.source_states}
        target = {self._state_key(state): state for state in plan.setup.target_states}
        ipr_sites: list[IPRSite] = []
        sorted_teeth = sorted(source, key=str)
        for tooth_a, tooth_b in zip(sorted_teeth, sorted_teeth[1:], strict=False):
            if plan.planning_mode == "clinical_fdi" and tooth_a // 10 != tooth_b // 10:
                continue
            if plan.planning_mode == "semantic_only_experimental":
                if source[tooth_a].arch != source[tooth_b].arch:
                    continue
            if plan.planning_mode not in ("clinical_fdi", "semantic_only_experimental"):
                continue
            ipr_sites.append(
                self._ipr_site(
                    plan, source[tooth_a], source[tooth_b], target[tooth_a], target[tooth_b]
                )
            )
        attachment_sites = tuple(
            self._attachment_site(plan, state)
            for state in sorted(target.values(), key=lambda item: str(self._state_key(item)))
            if any(
                value != 0.0
                for value in (
                    state.movement.rotation,
                    state.movement.tip,
                    state.movement.torque,
                )
            )
        )
        warnings = tuple(warning for site in ipr_sites for warning in site.warnings) + tuple(
            warning for site in attachment_sites for warning in site.warnings
        )
        proposal_id = self._hash(
            {
                "plan": plan.plan_id,
                "version": plan.version_id,
                "ipr": [self._ipr_payload(site) for site in ipr_sites],
                "attachments": [self._attachment_payload(site) for site in attachment_sites],
            }
        )
        history = () if previous is None else previous.history + (previous.proposal_id,)
        ipr = IPRProposal(
            proposal_id=proposal_id + ":ipr",
            plan_id=plan.plan_id,
            version_id=plan.version_id,
            sites=tuple(ipr_sites),
            status=ProposalStatus.NEEDS_REVIEW if ipr_sites else ProposalStatus.GENERATED,
            warnings=warnings,
            provenance=DataProvenance.GENERATED,
            fixture=plan.fixture,
            history=history,
        )
        attachments = AttachmentProposal(
            proposal_id=proposal_id + ":attachments",
            plan_id=plan.plan_id,
            version_id=plan.version_id,
            sites=attachment_sites,
            status=ProposalStatus.NEEDS_REVIEW if attachment_sites else ProposalStatus.GENERATED,
            warnings=warnings,
            provenance=DataProvenance.GENERATED,
            fixture=plan.fixture,
            history=history,
        )
        return TreatmentProposalResult(
            proposal_id=proposal_id,
            plan_id=plan.plan_id,
            version_id=plan.version_id,
            ipr=ipr,
            attachments=attachments,
            provenance=DataProvenance.GENERATED,
            fixture=plan.fixture,
            warnings=warnings,
            history=history,
        )

    def modify_ipr(
        self,
        result: TreatmentProposalResult,
        site_id: str,
        proposed_amount: float | None,
    ) -> TreatmentProposalResult:
        if proposed_amount is not None and proposed_amount < 0:
            raise TreatmentProposalError("IPR amount cannot be negative")
        site = next((site for site in result.ipr.sites if site.site_id == site_id), None)
        if site is None:
            raise TreatmentProposalError(f"Unknown IPR site: {site_id}")
        updated = replace(
            site, proposed_amount=proposed_amount, status=ProposalStatus.DOCTOR_MODIFIED
        )
        return self._replace_ipr(
            result, tuple(updated if item.site_id == site_id else item for item in result.ipr.sites)
        )

    def set_ipr_status(
        self, result: TreatmentProposalResult, site_id: str, status: ProposalStatus
    ) -> TreatmentProposalResult:
        site = next((site for site in result.ipr.sites if site.site_id == site_id), None)
        if site is None:
            raise TreatmentProposalError(f"Unknown IPR site: {site_id}")
        updated = replace(site, status=status)
        return self._replace_ipr(
            result, tuple(updated if item.site_id == site_id else item for item in result.ipr.sites)
        )

    def set_attachment_status(
        self, result: TreatmentProposalResult, site_id: str, status: ProposalStatus
    ) -> TreatmentProposalResult:
        site = next((site for site in result.attachments.sites if site.site_id == site_id), None)
        if site is None:
            raise TreatmentProposalError(f"Unknown attachment site: {site_id}")
        updated = replace(site, status=status)
        attachments = replace(
            result.attachments,
            sites=tuple(
                updated if item.site_id == site_id else item for item in result.attachments.sites
            ),
            status=ProposalStatus.DOCTOR_MODIFIED,
        )
        return replace(
            result,
            attachments=attachments,
            proposal_id=self._hash_result(result, attachments=attachments),
        )

    def reset(self, generated: TreatmentProposalResult) -> TreatmentProposalResult:
        return generated

    def _ipr_site(self, plan, source_a, source_b, target_a, target_b):
        warning = ProposalWarning(
            "clinical_review_required",
            "Geometric space delta is not a clinically approved IPR recommendation.",
        )
        try:
            current = float(
                np.linalg.norm(
                    np.asarray(source_a.source_vertices).mean(axis=0)
                    - np.asarray(source_b.source_vertices).mean(axis=0)
                )
            )
            target = float(
                np.linalg.norm(
                    np.asarray(target_a.target_vertices).mean(axis=0)
                    - np.asarray(target_b.target_vertices).mean(axis=0)
                )
            )
        except (TypeError, ValueError):
            current = target = None
        status = (
            ProposalStatus.NEEDS_REVIEW
            if current is not None and target is not None
            else ProposalStatus.UNABLE_TO_DETERMINE
        )
        required = (
            max(current - target, 0.0) if current is not None and target is not None else None
        )
        site_key = f"{plan.version_id}:ipr:{source_a.tooth_number}:{source_b.tooth_number}"
        return IPRSite(
            site_id=self._hash(site_key),
            tooth_a=source_a.tooth_number,
            tooth_b=source_b.tooth_number,
            current_measurement=IPRMeasurement(current, "model units", "centroid distance", status),
            target_measurement=IPRMeasurement(target, "model units", "centroid distance", status),
            required_space=required,
            proposed_amount=required,
            confidence=0.5 if status is ProposalStatus.NEEDS_REVIEW else 0.0,
            status=status,
            warnings=(warning,)
            if status is ProposalStatus.NEEDS_REVIEW
            else (
                ProposalWarning(
                    "insufficient_geometry", "Required site geometry could not be determined."
                ),
            ),
            provenance=DataProvenance.GENERATED,
            fixture=plan.fixture,
        )

    def _attachment_site(self, plan, state):
        warning = ProposalWarning(
            "attachment_dimensions_undetermined",
            "Attachment shape and dimensions require explicit doctor review; no "
            "validated geometry is generated.",
        )
        return AttachmentSite(
            site_id=self._hash(f"{plan.version_id}:attachment:{state.tooth_number}"),
            tooth_number=state.tooth_number,
            attachment_type=AttachmentType.UNDETERMINED,
            reference_point=tuple(
                float(value) for value in np.asarray(state.target_vertices).mean(axis=0)
            ),
            orientation=(
                state.coordinate_system.lateral_axis,
                state.coordinate_system.anterior_axis,
                state.coordinate_system.vertical_axis,
            ),
            dimensions=None,
            reason="Explicit tooth movement includes angular correction.",
            confidence=0.25,
            status=ProposalStatus.NEEDS_REVIEW,
            warnings=(warning,),
            provenance=DataProvenance.GENERATED,
            fixture=plan.fixture,
        )

    def _empty_result(self, plan, warning, previous):
        proposal_id = self._hash(
            {"plan": plan.plan_id, "version": plan.version_id, "warning": warning.code}
        )
        history = () if previous is None else previous.history + (previous.proposal_id,)
        ipr = IPRProposal(
            proposal_id + ":ipr",
            plan.plan_id,
            plan.version_id,
            (),
            ProposalStatus.UNABLE_TO_DETERMINE,
            (warning,),
            plan.provenance,
            plan.fixture,
            history,
        )
        attachments = AttachmentProposal(
            proposal_id + ":attachments",
            plan.plan_id,
            plan.version_id,
            (),
            ProposalStatus.UNABLE_TO_DETERMINE,
            (warning,),
            plan.provenance,
            plan.fixture,
            history,
        )
        return TreatmentProposalResult(
            proposal_id,
            plan.plan_id,
            plan.version_id,
            ipr,
            attachments,
            plan.provenance,
            plan.fixture,
            (warning,),
            history,
        )

    @staticmethod
    def _state_key(state):
        return (
            state.tooth_ref
            if state.planning_mode == "semantic_only_experimental"
            else state.tooth_number
        )

    def _replace_ipr(self, result, sites):
        ipr = replace(result.ipr, sites=sites, status=ProposalStatus.DOCTOR_MODIFIED)
        return replace(result, ipr=ipr, proposal_id=self._hash_result(result, ipr=ipr))

    def _hash_result(self, result, *, ipr=None, attachments=None):
        return self._hash(
            {
                "plan": result.plan_id,
                "version": result.version_id,
                "ipr": [self._ipr_payload(site) for site in (ipr or result.ipr).sites],
                "attachments": [
                    self._attachment_payload(site)
                    for site in (attachments or result.attachments).sites
                ],
            }
        )

    @staticmethod
    def _ipr_payload(site):
        return {
            "id": site.site_id,
            "a": site.tooth_a,
            "b": site.tooth_b,
            "amount": site.proposed_amount,
            "status": site.status.value,
        }

    @staticmethod
    def _attachment_payload(site):
        return {
            "id": site.site_id,
            "tooth": site.tooth_number,
            "type": site.attachment_type.value,
            "status": site.status.value,
        }

    @staticmethod
    def _hash(value):
        payload = (
            value
            if isinstance(value, str)
            else json.dumps(value, sort_keys=True, separators=(",", ":"))
        )
        return hashlib.sha256(payload.encode()).hexdigest()
