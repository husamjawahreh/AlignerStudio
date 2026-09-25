"""HTTP application state for existing treatment engines; no clinical logic lives here."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, replace as dataclass_replace
from pathlib import Path
from time import perf_counter
from typing import Any

from domain.tooth.identification import ArchType
from domain.treatment_plan.input import TreatmentPlanningInput
from domain.treatment_plan.manufacturing import build_manufacturing_boundary_report
from domain.treatment_plan.proposals import ProposalStatus
from domain.treatment_plan.setup import ToothMovement, TreatmentPlanProposal
from domain.treatment_plan.staging import StagingConfiguration, StagingResult
from domain.treatment_plan.validation import TreatmentValidationReport, ValidationStatus
from engines.arrangement.identification import ToothIdentificationEngine
from engines.export import TreatmentExportEngine, TreatmentExportPackage
from engines.planning.editing import TreatmentEditingApplication
from engines.planning.intelligence import (
    AdvancedPlanningIntelligenceEngine,
    AdvancedPlanningIntelligenceResult,
)
from engines.planning.proposals import TreatmentProposalEngine
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.setup_versioning import (
    TreatmentSetupVersionSnapshot,
    append_immutable_version,
    build_treatment_setup_payload,
    compare_proposals,
    find_version,
    snapshot_from_session_parts,
)
from engines.planning.staging_engine import TreatmentStagingEngine
from engines.planning.smart_staging_engine import (
    SmartStagingEngine,
    SmartStagingPlan,
    SmartStagingVersionSnapshot,
    append_staging_version,
    build_smart_staging_review_payload,
    evaluate_freshness,
    find_staging_version,
    with_freshness,
)
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)
from engines.validation.review_summary import build_validation_review_summary

from app.engineering_fixture import demo_objectives, synthetic_upper_arch
from app.session_persistence import delete_session, load_session, save_session
from domain.treatment_plan.setup_v2 import stable_setup_plan_id
from domain.treatment_plan.smart_staging import StagingFreshness

logger = logging.getLogger(__name__)


class TreatmentSessionError(ValueError):
    """Raised when a requested treatment session is unavailable or invalid."""


@dataclass
class TreatmentSession:
    proposal: TreatmentPlanProposal
    staging: StagingResult
    validation: TreatmentValidationReport
    adjuncts: Any
    source_kind: str = "development_treatment_fixture"
    experimental: bool = True
    planning_mode: str = "clinical_fdi"
    intelligence: AdvancedPlanningIntelligenceResult | None = None
    # WP-05 Treatment Setup 2.0 lineage (defaults keep pickle-compat with older sessions).
    parent_version_id: str | None = None
    version_history: tuple = ()
    # WP-06 Smart Staging lineage.
    smart_staging: Any = None
    staging_history: tuple = ()
    # WP-07 Clinical tools binding (setup/staging versions that produced adjuncts).
    clinical_tools_setup_version_id: str | None = None
    clinical_tools_staging_version_id: str | None = None


class TreatmentSessionStore:
    """Process-local treatment session store with durable restart recovery."""

    def __init__(self) -> None:
        self._sessions: dict[str, TreatmentSession] = {}
        self._planner = TreatmentPlanningEngine()
        self._stager = TreatmentStagingEngine()
        self._smart_stager = SmartStagingEngine(stager=self._stager)
        self._validator = GeometricValidationEngine()
        self._proposals = TreatmentProposalEngine()
        self._editing = TreatmentEditingApplication()
        self._intelligence = AdvancedPlanningIntelligenceEngine(
            planner=self._planner,
            stager=self._stager,
            validator=self._validator,
            validation_config=GeometricValidationConfiguration(1.0, 0.001, 0.0),
        )

    def _remember(self, case_id: str, session: TreatmentSession) -> TreatmentSession:
        self._sessions[case_id] = session
        save_session(case_id, session)
        return session

    def create_engineering_fixture(self, case_id: str) -> TreatmentSession:
        """Create an explicit engineering fixture, never a substitute for segmentation."""
        identification = ToothIdentificationEngine().identify(
            synthetic_upper_arch(), ArchType.UPPER
        )
        proposal = self._planner.generate(case_id, identification, demo_objectives())
        session = self._compose(proposal)
        return self._remember(case_id, session)

    def create_from_treatment_input(
        self,
        case_id: str,
        treatment_input: TreatmentPlanningInput,
        objectives,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> TreatmentSession:
        """Compose existing treatment engines from reviewed domain input."""
        proposal = self._planner.generate_from_input(case_id, treatment_input, objectives)
        session = self._compose(proposal, progress_callback=progress_callback)
        return self._remember(case_id, session)

    def get(self, case_id: str) -> TreatmentSession:
        session = self._sessions.get(case_id)
        if session is not None:
            return session
        recovered = load_session(case_id)
        if isinstance(recovered, TreatmentSession):
            self._sessions[case_id] = recovered
            return recovered
        raise TreatmentSessionError("Treatment data is unavailable for this case")

    def clear(self) -> None:
        """Drop in-memory sessions (tests). Durable files are removed when present."""
        for case_id in list(self._sessions):
            delete_session(case_id)
        self._sessions.clear()

    def apply_edit(
        self,
        case_id: str,
        tooth_number: int | str,
        movement: dict[str, float],
        *,
        reason: str | None = None,
        restage: bool = True,
    ) -> TreatmentSession:
        """P4: Doctor Edit → Target Update → (optional) Staging Rebuild → Validation.

        When ``restage=False``, the target setup updates and existing staging is marked
        stale until an explicit regenerate (WP-06). Default ``restage=True`` preserves
        P4/WP-05 coupled restage behavior.
        """
        from domain.movement.interaction import normalize_edit_reason

        session = self._normalize_session(self.get(case_id))
        reason_value = normalize_edit_reason(reason)
        if restage:
            result = self._editing.apply_edit_and_recalculate(
                session.proposal,
                tooth_number,
                ToothMovement(**{k: v for k, v in movement.items() if k != "reason"}),
                self._staging_configuration(),
                GeometricValidationConfiguration(1.0, 0.001, 0.0),
                reason=reason_value,
            )
            session = self._session_from_result(session, result)
            session = self._attach_intelligence(session)
            return self._remember(case_id, session)

        edited = self._editing.apply_edit(
            session.proposal,
            tooth_number,
            ToothMovement(**{k: v for k, v in movement.items() if k != "reason"}),
            reason=reason_value,
        )
        if getattr(session, "smart_staging", None) is not None:
            stale_plan = with_freshness(session.smart_staging, edited.version_id)
        else:
            stale_plan = None
        # WP-07: preserve adjuncts; do not silently rebase clinical tools onto the new setup.
        session = TreatmentSession(
            proposal=edited,
            staging=session.staging,
            validation=session.validation,
            adjuncts=session.adjuncts,
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
            parent_version_id=session.proposal.version_id,
            version_history=session.version_history,
            smart_staging=stale_plan,
            staging_history=getattr(session, "staging_history", ()) or (),
            clinical_tools_setup_version_id=getattr(
                session, "clinical_tools_setup_version_id", None
            ),
            clinical_tools_staging_version_id=getattr(
                session, "clinical_tools_staging_version_id", None
            ),
        )
        session = self._attach_intelligence(session)
        return self._remember(case_id, session)

    def regenerate_staging(
        self,
        case_id: str,
        *,
        description: str = "",
        author_source: str = "doctor",
    ) -> TreatmentSession:
        """Explicit WP-06 regenerate: restage + validate against current setup version.

        WP-07: preserves clinical-tool adjuncts and marks them stale vs the new staging
        version until an explicit clinical-tools regenerate.
        """
        session = self._normalize_session(self.get(case_id))
        parent_id = (
            session.smart_staging.meta.staging_version_id
            if session.smart_staging is not None
            else None
        )
        result = self._editing.recalculate(
            session.proposal,
            self._staging_configuration(),
            GeometricValidationConfiguration(1.0, 0.001, 0.0),
        )
        plan = self._smart_stager.wrap(
            result.proposal,
            result.staging,
            self._staging_configuration(),
            validation=result.validation,
            parent_staging_version_id=parent_id,
            author_source=author_source,
            description=description or "Explicit staging regenerate",
        )
        history = append_staging_version(
            tuple(session.staging_history),
            SmartStagingVersionSnapshot(plan=plan, validation=result.validation),
        )
        session = TreatmentSession(
            proposal=result.proposal,
            staging=result.staging,
            validation=result.validation,
            adjuncts=session.adjuncts,
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
            intelligence=session.intelligence,
            parent_version_id=session.parent_version_id,
            version_history=session.version_history,
            smart_staging=plan,
            staging_history=history,
            clinical_tools_setup_version_id=getattr(
                session, "clinical_tools_setup_version_id", None
            ),
            clinical_tools_staging_version_id=getattr(
                session, "clinical_tools_staging_version_id", None
            ),
        )
        session = self._attach_intelligence(session)
        return self._remember(case_id, session)

    def save_staging_version(
        self,
        case_id: str,
        *,
        description: str = "",
        author_source: str = "doctor",
    ) -> TreatmentSession:
        """Freeze the current smart staging plan as an immutable staging version."""
        session = self._normalize_session(self.get(case_id))
        if session.smart_staging is None:
            session = self.regenerate_staging(
                case_id, description=description or "Initial staging save", author_source=author_source
            )
            session = self._normalize_session(session)
        plan = session.smart_staging
        if plan is None:
            raise TreatmentSessionError("Smart staging plan is unavailable")
        freshness = evaluate_freshness(
            source_setup_version_id=plan.meta.source_setup_version_id,
            current_setup_version_id=session.proposal.version_id,
            has_staging=True,
        )
        if freshness is StagingFreshness.STALE:
            raise TreatmentSessionError(
                "Staging is stale relative to the current Treatment Setup version; regenerate first"
            )
        snapshot = SmartStagingVersionSnapshot(plan=plan, validation=session.validation)
        history = append_staging_version(tuple(session.staging_history), snapshot)
        session = dataclass_replace(session, staging_history=history)
        return self._remember(case_id, session)

    def list_staging_versions(self, case_id: str) -> list[dict]:
        session = self._normalize_session(self.get(case_id))
        return [item.plan.meta.payload() for item in session.staging_history]

    def restore_staging_version(self, case_id: str, staging_version_id: str) -> TreatmentSession:
        """Restore an immutable staging snapshot into the working session."""
        session = self._normalize_session(self.get(case_id))
        snapshot = find_staging_version(tuple(session.staging_history), staging_version_id)
        if snapshot is None:
            raise TreatmentSessionError(f"Unknown staging version: {staging_version_id}")
        plan = with_freshness(snapshot.plan, session.proposal.version_id)
        validation = snapshot.validation or session.validation
        session = TreatmentSession(
            proposal=session.proposal,
            staging=snapshot.plan.staging,
            validation=validation,
            adjuncts=session.adjuncts,
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
            intelligence=session.intelligence,
            parent_version_id=session.parent_version_id,
            version_history=session.version_history,
            smart_staging=plan,
            staging_history=session.staging_history,
            # Restored staging may diverge from clinical-tool binding → stale until regenerate.
            clinical_tools_setup_version_id=getattr(
                session, "clinical_tools_setup_version_id", None
            ),
            clinical_tools_staging_version_id=getattr(
                session, "clinical_tools_staging_version_id", None
            ),
        )
        return self._remember(case_id, session)

    def apply_edits(
        self,
        case_id: str,
        edits: list[tuple[int | str, dict[str, float]]],
        *,
        reason: str | None = None,
    ) -> TreatmentSession:
        """WP-05 multi-tooth target edit — one rebuild/validate pass, per-tooth provenance."""
        from domain.movement.interaction import normalize_edit_reason

        session = self.get(case_id)
        normalized = [
            (
                tooth_key,
                ToothMovement(**{k: v for k, v in movement.items() if k != "reason"}),
            )
            for tooth_key, movement in edits
        ]
        result = self._editing.apply_edits_and_recalculate(
            session.proposal,
            normalized,
            self._staging_configuration(),
            GeometricValidationConfiguration(1.0, 0.001, 0.0),
            reason=normalize_edit_reason(reason),
        )
        session = self._session_from_result(session, result)
        session = self._attach_intelligence(session)
        return self._remember(case_id, session)

    def save_version(
        self,
        case_id: str,
        *,
        description: str = "",
        author_source: str = "doctor",
    ) -> TreatmentSession:
        """Freeze the current working setup as an immutable version snapshot."""
        session = self._normalize_session(self.get(case_id))
        snapshot = snapshot_from_session_parts(
            proposal=session.proposal,
            staging=session.staging,
            validation=session.validation,
            parent_version_id=session.parent_version_id,
            description=description or "Saved treatment setup version",
            author_source=author_source,
        )
        history = append_immutable_version(tuple(session.version_history), snapshot)
        session = dataclass_replace(session, version_history=history)
        return self._remember(case_id, session)

    def list_versions(self, case_id: str) -> list[dict]:
        session = self._normalize_session(self.get(case_id))
        return [item.meta.payload() for item in session.version_history]

    def restore_version(self, case_id: str, version_id: str) -> TreatmentSession:
        """Restore an immutable snapshot into the working session (does not mutate the snapshot)."""
        session = self._normalize_session(self.get(case_id))
        snapshot = find_version(tuple(session.version_history), version_id)
        if snapshot is None:
            raise TreatmentSessionError(f"Unknown treatment setup version: {version_id}")
        restored = TreatmentSession(
            proposal=snapshot.proposal,
            staging=snapshot.staging,
            validation=snapshot.validation,
            adjuncts=self._proposals.generate(snapshot.proposal, previous=session.adjuncts),
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
            intelligence=session.intelligence,
            parent_version_id=snapshot.meta.version_id,
            version_history=session.version_history,
            staging_history=getattr(session, "staging_history", ()) or (),
        )
        # Rebuild smart staging binding for the restored setup version (no silent rebase).
        plan = self._smart_stager.wrap(
            snapshot.proposal,
            snapshot.staging,
            self._staging_configuration(),
            validation=snapshot.validation,
            author_source="system_restore",
            description="Restored with Treatment Setup version",
        )
        plan = with_freshness(plan, snapshot.proposal.version_id)
        restored = dataclass_replace(
            restored,
            smart_staging=plan,
            clinical_tools_setup_version_id=snapshot.proposal.version_id,
            clinical_tools_staging_version_id=plan.meta.staging_version_id,
        )
        restored = self._attach_intelligence(restored)
        return self._remember(case_id, restored)

    def compare_versions(
        self, case_id: str, left_version_id: str, right_version_id: str
    ) -> dict:
        session = self._normalize_session(self.get(case_id))
        left = self._resolve_compare_side(session, left_version_id)
        right = self._resolve_compare_side(session, right_version_id)
        return compare_proposals(
            left["proposal"],
            right["proposal"],
            left_version_id=left_version_id,
            right_version_id=right_version_id,
            left_validation_status=left["validation_status"],
            right_validation_status=right["validation_status"],
        ).payload()

    def _resolve_compare_side(self, session: TreatmentSession, version_id: str) -> dict:
        if version_id in ("current", "working", session.proposal.version_id):
            return {
                "proposal": session.proposal,
                "validation_status": session.validation.status.value,
            }
        if version_id == "target":
            return {
                "proposal": session.proposal,
                "validation_status": session.validation.status.value,
            }
        snapshot = find_version(tuple(session.version_history), version_id)
        if snapshot is None:
            raise TreatmentSessionError(f"Unknown treatment setup version: {version_id}")
        return {
            "proposal": snapshot.proposal,
            "validation_status": snapshot.validation.status.value,
        }

    def _session_from_result(
        self,
        session: TreatmentSession,
        result,
        *,
        staging_author_source: str = "system",
        staging_description: str = "",
        parent_staging_version_id: str | None = None,
    ) -> TreatmentSession:
        session = self._normalize_session(session)
        parent_staging = parent_staging_version_id
        if parent_staging is None and session.smart_staging is not None:
            parent_staging = session.smart_staging.meta.staging_version_id
        plan = self._smart_stager.wrap(
            result.proposal,
            result.staging,
            self._staging_configuration(),
            validation=result.validation,
            parent_staging_version_id=parent_staging,
            author_source=staging_author_source,
            description=staging_description
            or "Staging coupled to Treatment Setup edit/recalculate",
        )
        history = append_staging_version(
            tuple(session.staging_history),
            SmartStagingVersionSnapshot(plan=plan, validation=result.validation),
        )
        adjuncts = self._proposals.generate(result.proposal, previous=session.adjuncts)
        return TreatmentSession(
            proposal=result.proposal,
            staging=result.staging,
            validation=result.validation,
            adjuncts=adjuncts,
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
            parent_version_id=session.proposal.version_id,
            version_history=session.version_history,
            smart_staging=plan,
            staging_history=history,
            clinical_tools_setup_version_id=result.proposal.version_id,
            clinical_tools_staging_version_id=plan.meta.staging_version_id,
        )

    @staticmethod
    def _normalize_session(session: TreatmentSession) -> TreatmentSession:
        parent = getattr(session, "parent_version_id", None)
        history = getattr(session, "version_history", ()) or ()
        if not isinstance(history, tuple):
            history = tuple(history)
        staging_history = getattr(session, "staging_history", ()) or ()
        if not isinstance(staging_history, tuple):
            staging_history = tuple(staging_history)
        smart_staging = getattr(session, "smart_staging", None)
        clinical_setup = getattr(session, "clinical_tools_setup_version_id", None)
        clinical_staging = getattr(session, "clinical_tools_staging_version_id", None)
        # Older pickled sessions may lack clinical-tool binding — bind to adjuncts version.
        if clinical_setup is None and getattr(session, "adjuncts", None) is not None:
            clinical_setup = getattr(session.adjuncts, "version_id", None)
        if (
            parent is session.parent_version_id
            and history is session.version_history
            and staging_history is getattr(session, "staging_history", ())
            and smart_staging is getattr(session, "smart_staging", None)
            and clinical_setup is getattr(session, "clinical_tools_setup_version_id", None)
            and clinical_staging is getattr(session, "clinical_tools_staging_version_id", None)
        ):
            return session
        return dataclass_replace(
            session,
            parent_version_id=parent,
            version_history=history,
            staging_history=staging_history,
            smart_staging=smart_staging,
            clinical_tools_setup_version_id=clinical_setup,
            clinical_tools_staging_version_id=clinical_staging,
        )

    def reset_tooth(self, case_id: str, tooth_number: int | str) -> TreatmentSession:
        session = self.get(case_id)
        proposal = self._editing.reset_tooth(session.proposal, tooth_number)
        result = self._editing.recalculate(
            proposal,
            self._staging_configuration(),
            GeometricValidationConfiguration(1.0, 0.001, 0.0),
        )
        session = self._session_from_result(session, result)
        session = self._attach_intelligence(session)
        return self._remember(case_id, session)

    def reset_all(self, case_id: str) -> TreatmentSession:
        session = self.get(case_id)
        proposal = self._editing.reset_all(session.proposal)
        result = self._editing.recalculate(
            proposal,
            self._staging_configuration(),
            GeometricValidationConfiguration(1.0, 0.001, 0.0),
        )
        session = self._session_from_result(session, result)
        session = self._attach_intelligence(session)
        return self._remember(case_id, session)

    def recalculate(self, case_id: str) -> TreatmentSession:
        session = self.get(case_id)
        result = self._editing.recalculate(
            session.proposal,
            self._staging_configuration(),
            GeometricValidationConfiguration(1.0, 0.001, 0.0),
        )
        session = self._session_from_result(session, result)
        session = self._attach_intelligence(session)
        return self._remember(case_id, session)

    def export(self, case_id: str, destination: Path) -> TreatmentExportPackage:
        session = self.get(case_id)
        return TreatmentExportEngine().export(
            destination, session.proposal, session.staging, session.validation, session.adjuncts
        )

    def set_ipr_status(self, case_id: str, site_id: str, status: str) -> TreatmentSession:
        session = self.get(case_id)
        adjuncts = self._proposals.set_ipr_status(
            session.adjuncts, site_id, ProposalStatus(status)
        )
        session = dataclass_replace(session, adjuncts=adjuncts)
        return self._remember(case_id, session)

    def modify_ipr_amount(self, case_id: str, site_id: str, amount: float) -> TreatmentSession:
        session = self.get(case_id)
        adjuncts = self._proposals.modify_ipr(session.adjuncts, site_id, amount)
        session = dataclass_replace(session, adjuncts=adjuncts)
        return self._remember(case_id, session)

    def set_attachment_status(self, case_id: str, site_id: str, status: str) -> TreatmentSession:
        session = self.get(case_id)
        adjuncts = self._proposals.set_attachment_status(
            session.adjuncts, site_id, ProposalStatus(status)
        )
        session = dataclass_replace(session, adjuncts=adjuncts)
        return self._remember(case_id, session)

    def reset_proposals(self, case_id: str) -> TreatmentSession:
        """Regenerate adjunct proposals from the current plan version (no invented geometry)."""
        return self.regenerate_clinical_tools(case_id)

    def regenerate_clinical_tools(self, case_id: str) -> TreatmentSession:
        """WP-07 explicit clinical-tools regenerate — binds to current setup/staging versions."""
        session = self._normalize_session(self.get(case_id))
        adjuncts = self._proposals.generate(session.proposal, previous=session.adjuncts)
        staging_version_id = None
        if session.smart_staging is not None:
            staging_version_id = session.smart_staging.meta.staging_version_id
        session = dataclass_replace(
            session,
            adjuncts=adjuncts,
            clinical_tools_setup_version_id=session.proposal.version_id,
            clinical_tools_staging_version_id=staging_version_id,
        )
        return self._remember(case_id, session)

    def verify_export(self, case_id: str, destination: Path) -> dict[str, Any]:
        """Export then verify package hashes; returns auditable verification report."""
        package = self.export(case_id, destination)
        return TreatmentExportEngine().verify_package(package.zip_path)

    def reopen_export_for_audit(self, case_id: str, destination: Path) -> dict[str, Any]:
        """Export then reopen the ZIP for audit/verify (not full session re-import)."""
        package = self.export(case_id, destination)
        return TreatmentExportEngine().reopen_for_audit(package.zip_path)

    def select_setup_alternative(self, case_id: str, alternative_id: str) -> TreatmentSession:
        """Doctor decision: accept a validated intelligence candidate as the active setup."""
        from domain.treatment_plan.intelligence import DecisionState, SetupAlternativeSummary
        from engines.planning.intelligence import IntelligenceCandidate

        session = self.ensure_planning_intelligence(case_id)
        if session.intelligence is None or not session.intelligence.candidates:
            raise TreatmentSessionError("No setup alternatives are available for this case")
        match = next(
            (
                item
                for item in session.intelligence.candidates
                if item.summary.alternative_id == alternative_id
            ),
            None,
        )
        if match is None:
            raise TreatmentSessionError(f"Unknown setup alternative: {alternative_id}")
        if match.summary.contract.decision_state.value == "rejected_by_validation":
            raise TreatmentSessionError(
                "Alternative was rejected by deterministic geometric validation and "
                "cannot be activated."
            )
        accepted_contract = dataclass_replace(
            match.summary.contract, decision_state=DecisionState.ACCEPTED_BY_DOCTOR
        )
        updated_candidates: list[IntelligenceCandidate] = []
        for item in session.intelligence.candidates:
            is_active = item.summary.alternative_id == alternative_id
            summary = SetupAlternativeSummary(
                alternative_id=item.summary.alternative_id,
                strategy=item.summary.strategy,
                label=item.summary.label,
                contract=accepted_contract if is_active else item.summary.contract,
                collision_count=item.summary.collision_count,
                proximity_count=item.summary.proximity_count,
                contact_count=item.summary.contact_count,
                stage_count=item.summary.stage_count,
                is_active=is_active,
            )
            updated_candidates.append(
                IntelligenceCandidate(
                    summary=summary,
                    proposal=match.proposal if is_active else item.proposal,
                    staging=match.staging if is_active else item.staging,
                    validation=match.validation if is_active else item.validation,
                )
            )
        report = dataclass_replace(
            session.intelligence.report,
            alternatives=tuple(item.summary for item in updated_candidates),
        )
        intelligence = AdvancedPlanningIntelligenceResult(
            report=report, candidates=tuple(updated_candidates)
        )
        plan = self._smart_stager.wrap(
            match.proposal,
            match.staging,
            self._staging_configuration(),
            validation=match.validation,
            author_source="doctor",
            description=f"Activated setup alternative {alternative_id}",
        )
        session = TreatmentSession(
            proposal=match.proposal,
            staging=match.staging,
            validation=match.validation,
            adjuncts=self._proposals.generate(match.proposal, previous=session.adjuncts),
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
            intelligence=intelligence,
            parent_version_id=session.proposal.version_id,
            version_history=getattr(session, "version_history", ()) or (),
            smart_staging=plan,
            staging_history=append_staging_version(
                tuple(getattr(session, "staging_history", ()) or ()),
                SmartStagingVersionSnapshot(plan=plan, validation=match.validation),
            ),
            clinical_tools_setup_version_id=match.proposal.version_id,
            clinical_tools_staging_version_id=plan.meta.staging_version_id,
        )
        return self._remember(case_id, session)

    def ensure_planning_intelligence(self, case_id: str) -> TreatmentSession:
        """Expand assisted alternatives (validated) when only a baseline shell exists."""
        session = self.get(case_id)
        if session.intelligence is not None and len(session.intelligence.candidates) > 1:
            return session
        session = self._attach_intelligence(session, generate_alternatives=True)
        return self._remember(case_id, session)

    def _attach_intelligence(
        self, session: TreatmentSession, *, generate_alternatives: bool | None = None
    ) -> TreatmentSession:
        if generate_alternatives is None:
            # Keep real-case compose fast: multi-candidate validation is on-demand.
            generate_alternatives = session.source_kind != "validated_real_case"
        intelligence = self._intelligence.generate(
            session.proposal,
            session.staging,
            session.validation,
            staging_configuration=self._staging_configuration(),
            generate_alternatives=generate_alternatives,
        )
        return dataclass_replace(session, intelligence=intelligence)

    def _compose(
        self,
        proposal: TreatmentPlanProposal,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> TreatmentSession:
        def emit(progress: int, message: str) -> None:
            if progress_callback is not None:
                progress_callback(progress, message)

        emit(72, "Preparing geometric validation")
        staging_started = perf_counter()
        staging = self._stager.generate(proposal, self._staging_configuration())
        logger.info(
            "TREATMENT_STAGING_COMPLETED plan_id=%s duration_ms=%.1f stages=%d",
            proposal.plan_id,
            (perf_counter() - staging_started) * 1000,
            len(staging.stages),
        )
        emit(82, "Evaluating collisions and proximity")
        validation_started = perf_counter()
        validation = self._validator.validate(
            staging, GeometricValidationConfiguration(1.0, 0.001, 0.0)
        )
        logger.info(
            "GEOMETRIC_VALIDATION_COMPLETED plan_id=%s duration_ms=%.1f stages=%d status=%s",
            proposal.plan_id,
            (perf_counter() - validation_started) * 1000,
            len(validation.stage_results),
            validation.status.value,
        )
        emit(88, "Validating plan")
        session = TreatmentSession(
            proposal,
            staging,
            validation,
            self._proposals.generate(proposal),
            source_kind=(
                "validated_real_case"
                if proposal.planning_mode == "semantic_only_experimental"
                else ("development_treatment_fixture" if proposal.fixture else "treatment_result")
            ),
            experimental=True,
            planning_mode=proposal.planning_mode,
            parent_version_id=None,
            version_history=(),
            smart_staging=None,
            staging_history=(),
        )
        # Seed immutable baseline version for Treatment Setup 2.0 lineage.
        baseline = snapshot_from_session_parts(
            proposal=proposal,
            staging=staging,
            validation=validation,
            parent_version_id=None,
            description="Initial treatment setup",
            author_source="deterministic_planner",
        )
        plan = self._smart_stager.wrap(
            proposal,
            staging,
            self._staging_configuration(),
            validation=validation,
            author_source="deterministic_planner",
            description="Initial smart staging",
        )
        staging_snapshot = SmartStagingVersionSnapshot(plan=plan, validation=validation)
        session = dataclass_replace(
            session,
            version_history=append_immutable_version((), baseline),
            smart_staging=plan,
            staging_history=append_staging_version((), staging_snapshot),
            clinical_tools_setup_version_id=proposal.version_id,
            clinical_tools_staging_version_id=plan.meta.staging_version_id,
        )
        return self._attach_intelligence(session)

    @staticmethod
    def _staging_configuration() -> StagingConfiguration:
        configured_count = int(os.environ.get("ALIGNERSTUDIO_STAGE_COUNT", "3"))
        mode = os.environ.get("ALIGNERSTUDIO_STAGING_MODE", "macro")
        return StagingConfiguration(stage_count=max(2, configured_count), mode=mode)


def review_bundle(session: TreatmentSession) -> dict[str, Any]:
    """Translate domain data to the browser DTO without recreating treatment logic."""
    validation_by_stage = {item.stage_index: item for item in session.validation.stage_results}
    stages = []
    for stage in session.staging.stages:
        stage_validation = validation_by_stage[stage.stage_index]
        tooth_messages = {
            item.tooth_number: "; ".join((*item.warnings, *item.errors))
            for item in stage_validation.tooth_results
        }
        tooth_statuses = {
            item.tooth_number: item.status.value for item in stage_validation.tooth_results
        }
        # Count true findings only — never the number of evaluated AABB pair slots.
        collision_count = sum(
            1 for item in stage_validation.collision_results if item.intersects
        )
        proximity_count = sum(
            1 for item in stage_validation.proximity_results if item.status is ValidationStatus.WARNING
        )
        contact_count = sum(1 for item in stage_validation.contact_results if item.is_contact)
        stages.append(
            {
                "index": stage.stage_index,
                "stageId": stage.stage_id,
                "label": stage.label,
                "type": stage.stage_type,
                "metadata": dict(stage.metadata),
                "validationFindings": list(stage.validation_findings),
                "teeth": [
                    {
                        "instanceId": index,
                        "fdiNumber": state.tooth_number,
                        "toothRef": state.tooth_ref,
                        "semanticLabel": state.semantic_label,
                        "arch": _review_arch(state),
                        "confidence": 1.0,
                        "vertices": state.vertices,
                        "faces": state.final_target_faces,
                        "movement": _movement(state.movement.movement),
                        "rate": _movement(state.movement.rate),
                        "accumulated": _movement(state.movement.accumulated),
                        "limitStatus": state.movement.limit_status,
                        "coordinateSystem": {
                            "origin": list(state.coordinate_system.origin),
                            "lateral_axis": list(state.coordinate_system.lateral_axis),
                            "anterior_axis": list(state.coordinate_system.anterior_axis),
                            "vertical_axis": list(state.coordinate_system.vertical_axis),
                            "semantics": list(state.coordinate_system.semantics),
                        },
                        "movementReferenceFrame": {
                            "origin": list(state.coordinate_system.origin),
                            "lateral_axis": list(state.coordinate_system.lateral_axis),
                            "anterior_axis": list(state.coordinate_system.anterior_axis),
                            "vertical_axis": list(state.coordinate_system.vertical_axis),
                            "semantics": list(state.coordinate_system.semantics),
                        },
                        "validationStatus": tooth_statuses.get(
                            _review_tooth_key(state), "pass"
                        ),
                        "validationMessage": tooth_messages.get(
                            _review_tooth_key(state), "No geometric findings."
                        ),
                        "provenance": state.provenance.value,
                        "fixture": state.fixture,
                    }
                    for index, state in enumerate(stage.tooth_states)
                ],
                "validationStatus": stage_validation.status.value,
                "collisionCount": collision_count,
                "proximityCount": proximity_count,
                "contactCount": contact_count,
                "warnings": [*stage_validation.warnings, *stage_validation.errors],
                "validationFindings": [*stage_validation.warnings, *stage_validation.errors],
                "provenance": stage.provenance.value,
                "fixture": stage.fixture,
            }
        )
    movements = [
        state.movement
        for state in (session.proposal.setup.target_states if session.proposal.setup else ())
        if state.movement != ToothMovement()
    ]
    total_movement = sum(
        abs(item.translation_x)
        + abs(item.translation_y)
        + abs(item.translation_z)
        + abs(item.rotation)
        + abs(item.tip)
        + abs(item.torque)
        + abs(item.angulation)
        + abs(item.intrusion)
        + abs(item.extrusion)
        for item in movements
    )
    final_stage_index = len(session.staging.stages) - 1 if session.staging.stages else None
    from engines.planning.clinical_tools_engine import (
        build_clinical_tools_plan,
        serialize_attachment_site,
        serialize_ipr_site,
    )
    from domain.treatment_plan.setup_v2 import ReadinessState
    from app.intelligence_store import get_dental_intelligence_record
    from engines.occlusion.capability_engine import (
        build_advanced_anatomy_report,
        build_occlusion_anatomy_plan,
        build_occlusion_result,
    )
    from app.segmentation_store import get_segmentation_record

    current_staging_version_id = None
    if getattr(session, "smart_staging", None) is not None:
        current_staging_version_id = session.smart_staging.meta.staging_version_id
    clinical_plan = build_clinical_tools_plan(
        session.adjuncts,
        current_setup_version_id=session.proposal.version_id,
        current_staging_version_id=current_staging_version_id,
        bound_setup_version_id=getattr(session, "clinical_tools_setup_version_id", None),
        bound_staging_version_id=getattr(session, "clinical_tools_staging_version_id", None),
        has_validation=session.validation is not None,
        has_source_geometry=bool(
            session.proposal.setup and session.proposal.setup.source_states
        ),
    )

    # WP-08: occlusion + advanced anatomy capability for setup/staging consumers.
    occlusion_readiness_state = ReadinessState.NOT_AVAILABLE
    clinical_axes_readiness_state = ReadinessState.NOT_AVAILABLE
    occlusion_anatomy_payload = None
    intel = get_dental_intelligence_record(session.proposal.case_id)
    segmentation = get_segmentation_record(session.proposal.case_id)
    if segmentation and segmentation.get("status") == "completed":
        occlusion_result = build_occlusion_result(
            case_id=session.proposal.case_id,
            segmentation_record=segmentation,
            bound_setup_version_id=session.proposal.version_id,
            bound_staging_version_id=current_staging_version_id,
            current_setup_version_id=session.proposal.version_id,
            current_staging_version_id=current_staging_version_id,
        )
        tooth_summaries = None
        if isinstance(intel, dict):
            tooth_summaries = intel.get("teeth")
        anatomy = build_advanced_anatomy_report(
            case_id=session.proposal.case_id,
            segmentation_record=segmentation,
            tooth_intelligence_summaries=tooth_summaries if isinstance(tooth_summaries, list) else None,
        )
        plan = build_occlusion_anatomy_plan(
            occlusion=occlusion_result,
            advanced_anatomy=anatomy,
            setup_version_id=session.proposal.version_id,
            staging_version_id=current_staging_version_id,
        )
        occlusion_anatomy_payload = plan.payload()
        # Map WP-08 capability → setup readiness vocabulary.
        occ_map = {
            "unavailable": ReadinessState.NOT_AVAILABLE,
            "not_available": ReadinessState.NOT_AVAILABLE,
            "requires_review": ReadinessState.REQUIRES_REVIEW,
            "available": ReadinessState.AVAILABLE,
            "stale": ReadinessState.REQUIRES_REVIEW,
        }
        occlusion_readiness_state = occ_map.get(
            plan.occlusion_prerequisite.value, ReadinessState.NOT_AVAILABLE
        )
        clinical_axes_readiness_state = occ_map.get(
            plan.clinical_axes_prerequisite.value, ReadinessState.NOT_AVAILABLE
        )
    elif isinstance(intel, dict):
        readiness = intel.get("capability_readiness") or {}
        occ = readiness.get("occlusion_readiness")
        axis = readiness.get("axis_readiness")
        if occ == "requires_review":
            occlusion_readiness_state = ReadinessState.REQUIRES_REVIEW
        elif occ == "computed" or occ == "verified":
            occlusion_readiness_state = ReadinessState.AVAILABLE
        if axis == "requires_review":
            clinical_axes_readiness_state = ReadinessState.REQUIRES_REVIEW
        elif axis == "computed" or axis == "verified":
            clinical_axes_readiness_state = ReadinessState.AVAILABLE
        occ_value = (intel.get("occlusion") or {}).get("value")
        if isinstance(occ_value, dict) and occ_value.get("advanced_anatomy"):
            occlusion_anatomy_payload = {
                "contract_version": "occlusion_anatomy_binding_1.0",
                "occlusion": occ_value,
                "advanced_anatomy": occ_value.get("advanced_anatomy"),
                "prerequisites": {
                    "occlusion": occ_value.get("capability_state", "unavailable"),
                    "clinical_axes": clinical_axes_readiness_state.value,
                    "root_geometry": (occ_value.get("advanced_anatomy") or {}).get(
                        "root_geometry", "not_available"
                    ),
                    "landmarks": (occ_value.get("advanced_anatomy") or {}).get(
                        "landmark_geometry", "not_available"
                    ),
                },
                "freshness": occ_value.get("freshness", "unavailable"),
                "clinically_approved": False,
                "occlusion_validated": False,
            }

    validation_summary = build_validation_review_summary(
        session.proposal, session.staging, session.validation
    ).payload()
    manufacturing = build_manufacturing_boundary_report(
        has_stage_models=bool(session.staging.stages)
    ).payload()
    intelligence_payload = (
        session.intelligence.report.payload() if session.intelligence is not None else None
    )
    active_alternative = None
    if session.intelligence is not None:
        active_alternative = next(
            (item for item in session.intelligence.report.alternatives if item.is_active),
            None,
        )
    return {
        "stages": stages,
        "provenance": session.proposal.provenance.value,
        "fixture": session.proposal.fixture,
        "sourceKind": session.source_kind,
        "experimental": session.experimental,
        "planningMode": session.planning_mode,
        "planSummary": {
            "movedToothCount": len(movements),
            "totalMovement": total_movement,
            "notableConflicts": [
                warning
                for warning in session.proposal.warnings
                if "collision" in warning.lower() or "conflict" in warning.lower()
            ],
            "dataGaps": list(session.proposal.limitations),
            "warnings": list(session.proposal.warnings),
            "source": "deterministic planner",
            "doctorReviewRequired": True,
            "alternativeCount": (
                len(session.intelligence.report.alternatives)
                if session.intelligence is not None
                else 0
            ),
            "activeAlternativeStrategy": (
                active_alternative.strategy if active_alternative is not None else None
            ),
        },
        "validationSummary": validation_summary,
        "manufacturingBoundary": manufacturing,
        "planningIntelligence": intelligence_payload,
        "realDataAvailable": True,
        "proposalKind": session.proposal.proposal_kind.value,
        "planId": session.proposal.plan_id,
        "versionId": session.proposal.version_id,
        "parentVersionId": getattr(session, "parent_version_id", None),
        "setupPlanId": stable_setup_plan_id(session.proposal.case_id),
        "treatmentSetup": build_treatment_setup_payload(
            case_id=session.proposal.case_id,
            proposal=session.proposal,
            staging=session.staging,
            validation=session.validation,
            parent_version_id=getattr(session, "parent_version_id", None),
            version_history=tuple(getattr(session, "version_history", ()) or ()),
            source_kind=session.source_kind,
            occlusion_readiness=occlusion_readiness_state,
            clinical_axes_readiness=clinical_axes_readiness_state,
        ),
        "smartStaging": build_smart_staging_review_payload(
            getattr(session, "smart_staging", None),
            current_setup_version_id=session.proposal.version_id,
            staging_history=tuple(getattr(session, "staging_history", ()) or ()),
        ),
        "clinicalTools": clinical_plan.payload(),
        "occlusionAnatomy": occlusion_anatomy_payload,
        "stagingId": session.staging.staging_id,
        "editHistory": [
            {
                "editId": item.edit_id,
                "toothNumber": item.tooth_number,
                "previousMovement": _movement(item.previous_movement),
                "newMovement": _movement(item.new_movement),
                "timestamp": item.timestamp,
                "versionId": item.version_id,
                "provenance": item.provenance.value,
                "reason": item.reason,
                "source": "doctor",
            }
            for item in session.proposal.edit_history
        ],
        "iprSites": [
            serialize_ipr_site(item, display_stage=final_stage_index)
            for item in session.adjuncts.ipr.sites
        ],
        "attachmentSites": [
            serialize_attachment_site(item, display_stage=final_stage_index)
            for item in session.adjuncts.attachments.sites
        ],
    }


def manifest_header(package: TreatmentExportPackage) -> str:
    return json.dumps(json.loads(package.manifest_path.read_text()), separators=(",", ":"))


def _review_arch(state: Any) -> str:
    """Prefer explicit arch / tooth_ref; never invent FDI to classify arches."""
    if state.arch in ("upper", "lower"):
        return state.arch
    tooth_ref = state.tooth_ref or ""
    if tooth_ref.startswith("upper:"):
        return "upper"
    if tooth_ref.startswith("lower:"):
        return "lower"
    if state.tooth_number is not None:
        return "upper" if state.tooth_number < 30 else "lower"
    raise ValueError("Tooth state is missing arch classification")


def _review_tooth_key(state: Any) -> int | str:
    """Match GeometricValidationEngine tooth identity for per-tooth review lookup."""
    if state.tooth_number is not None:
        return state.tooth_number
    if state.tooth_ref:
        return state.tooth_ref
    raise ValueError("Tooth state is missing both tooth_number and tooth_ref")


def _movement(movement: ToothMovement) -> dict[str, float | bool]:
    return {
        "translationX": movement.translation_x,
        "translationY": movement.translation_y,
        "translationZ": movement.translation_z,
        "rotation": movement.rotation,
        "tip": movement.tip,
        "torque": movement.torque,
        "angulation": movement.angulation,
        "intrusion": movement.intrusion,
        "extrusion": movement.extrusion,
        "locked": movement.locked,
        "excluded": movement.excluded,
    }


treatment_sessions = TreatmentSessionStore()
