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
from engines.planning.staging_engine import TreatmentStagingEngine
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)
from engines.validation.review_summary import build_validation_review_summary

from app.engineering_fixture import demo_objectives, synthetic_upper_arch
from app.session_persistence import delete_session, load_session, save_session

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


class TreatmentSessionStore:
    """Process-local treatment session store with durable restart recovery."""

    def __init__(self) -> None:
        self._sessions: dict[str, TreatmentSession] = {}
        self._planner = TreatmentPlanningEngine()
        self._stager = TreatmentStagingEngine()
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
        self, case_id: str, tooth_number: int | str, movement: dict[str, float]
    ) -> TreatmentSession:
        """P4: Doctor Edit → Target Update → Staging Rebuild → Validation → Updated Review."""
        session = self.get(case_id)
        result = self._editing.apply_edit_and_recalculate(
            session.proposal,
            tooth_number,
            ToothMovement(**movement),
            self._staging_configuration(),
            GeometricValidationConfiguration(1.0, 0.001, 0.0),
        )
        session = TreatmentSession(
            proposal=result.proposal,
            staging=result.staging,
            validation=result.validation,
            adjuncts=self._proposals.generate(result.proposal, previous=session.adjuncts),
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
        )
        session = self._attach_intelligence(session)
        return self._remember(case_id, session)

    def reset_tooth(self, case_id: str, tooth_number: int | str) -> TreatmentSession:
        session = self.get(case_id)
        proposal = self._editing.reset_tooth(session.proposal, tooth_number)
        result = self._editing.recalculate(
            proposal,
            self._staging_configuration(),
            GeometricValidationConfiguration(1.0, 0.001, 0.0),
        )
        session = TreatmentSession(
            proposal=result.proposal,
            staging=result.staging,
            validation=result.validation,
            adjuncts=self._proposals.generate(result.proposal, previous=session.adjuncts),
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
        )
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
        session = TreatmentSession(
            proposal=result.proposal,
            staging=result.staging,
            validation=result.validation,
            adjuncts=self._proposals.generate(result.proposal, previous=session.adjuncts),
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
        )
        session = self._attach_intelligence(session)
        return self._remember(case_id, session)

    def recalculate(self, case_id: str) -> TreatmentSession:
        session = self.get(case_id)
        result = self._editing.recalculate(
            session.proposal,
            self._staging_configuration(),
            GeometricValidationConfiguration(1.0, 0.001, 0.0),
        )
        session = TreatmentSession(
            proposal=result.proposal,
            staging=result.staging,
            validation=result.validation,
            adjuncts=self._proposals.generate(result.proposal, previous=session.adjuncts),
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
        )
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
        session = self.get(case_id)
        adjuncts = self._proposals.generate(session.proposal)
        session = dataclass_replace(session, adjuncts=adjuncts)
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
        session = TreatmentSession(
            proposal=match.proposal,
            staging=match.staging,
            validation=match.validation,
            adjuncts=self._proposals.generate(match.proposal, previous=session.adjuncts),
            source_kind=session.source_kind,
            experimental=session.experimental,
            planning_mode=session.planning_mode,
            intelligence=intelligence,
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
            {
                "siteId": item.site_id,
                "toothA": item.tooth_a,
                "toothB": item.tooth_b,
                "currentDistance": item.current_measurement.value,
                "targetDistance": item.target_measurement.value,
                "proposedAmount": item.proposed_amount,
                "stage": item.stage_index
                if item.stage_index is not None
                else final_stage_index,
                "amountUnit": item.current_measurement.unit,
                "status": item.status.value,
                "warning": "; ".join(warning.message for warning in item.warnings),
                "fixture": item.fixture,
            }
            for item in session.adjuncts.ipr.sites
        ],
        "attachmentSites": [
            {
                "siteId": item.site_id,
                "toothNumber": item.tooth_number,
                "attachmentType": item.attachment_type.value,
                "referencePoint": item.reference_point,
                "reason": item.reason,
                "dimensions": item.dimensions,
                "stage": item.stage_index
                if item.stage_index is not None
                else final_stage_index,
                "generated": item.generated,
                "status": item.status.value,
                "warning": "; ".join(warning.message for warning in item.warnings),
                "fixture": item.fixture,
            }
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
