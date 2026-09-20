"""HTTP application state for existing treatment engines; no clinical logic lives here."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from domain.tooth.identification import ArchType
from domain.treatment_plan.setup import ToothMovement, TreatmentPlanProposal
from domain.treatment_plan.staging import StagingConfiguration, StagingResult
from domain.treatment_plan.validation import TreatmentValidationReport
from engines.arrangement.identification import ToothIdentificationEngine
from engines.export import TreatmentExportEngine, TreatmentExportPackage
from engines.planning.editing import TreatmentEditingApplication
from engines.planning.proposals import TreatmentProposalEngine
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.staging_engine import TreatmentStagingEngine
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)

from app.engineering_fixture import demo_objectives, synthetic_upper_arch


class TreatmentSessionError(ValueError):
    """Raised when a requested treatment session is unavailable or invalid."""


@dataclass
class TreatmentSession:
    proposal: TreatmentPlanProposal
    staging: StagingResult
    validation: TreatmentValidationReport
    adjuncts: Any


class TreatmentSessionStore:
    """Process-local treatment session store for the demo API."""

    def __init__(self) -> None:
        self._sessions: dict[str, TreatmentSession] = {}
        self._planner = TreatmentPlanningEngine()
        self._stager = TreatmentStagingEngine()
        self._validator = GeometricValidationEngine()
        self._proposals = TreatmentProposalEngine()
        self._editing = TreatmentEditingApplication()

    def create_engineering_fixture(self, case_id: str) -> TreatmentSession:
        """Create an explicit engineering fixture, never a substitute for segmentation."""
        identification = ToothIdentificationEngine().identify(
            synthetic_upper_arch(), ArchType.UPPER
        )
        proposal = self._planner.generate(case_id, identification, demo_objectives())
        session = self._compose(proposal)
        self._sessions[case_id] = session
        return session

    def get(self, case_id: str) -> TreatmentSession:
        session = self._sessions.get(case_id)
        if session is None:
            raise TreatmentSessionError("Treatment data is unavailable for this case")
        return session

    def apply_edit(
        self, case_id: str, tooth_number: int, movement: dict[str, float]
    ) -> TreatmentSession:
        session = self.get(case_id)
        proposal = self._editing.apply_edit(
            session.proposal, tooth_number, ToothMovement(**movement)
        )
        session = replace(session, proposal=proposal)
        self._sessions[case_id] = session
        return session

    def recalculate(self, case_id: str) -> TreatmentSession:
        session = self.get(case_id)
        result = self._editing.recalculate(
            session.proposal,
            StagingConfiguration(stage_count=3),
            GeometricValidationConfiguration(1.0, 0.001, 0.0),
        )
        session = TreatmentSession(
            proposal=result.proposal,
            staging=result.staging,
            validation=result.validation,
            adjuncts=self._proposals.generate(result.proposal, previous=session.adjuncts),
        )
        self._sessions[case_id] = session
        return session

    def export(self, case_id: str, destination: Path) -> TreatmentExportPackage:
        session = self.get(case_id)
        return TreatmentExportEngine().export(
            destination, session.proposal, session.staging, session.validation, session.adjuncts
        )

    def _compose(self, proposal: TreatmentPlanProposal) -> TreatmentSession:
        staging = self._stager.generate(proposal, StagingConfiguration(stage_count=3))
        validation = self._validator.validate(
            staging, GeometricValidationConfiguration(1.0, 0.001, 0.0)
        )
        return TreatmentSession(proposal, staging, validation, self._proposals.generate(proposal))


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
        stages.append(
            {
                "index": stage.stage_index,
                "stageId": stage.stage_id,
                "teeth": [
                    {
                        "fdiNumber": state.tooth_number,
                        "arch": "upper" if state.tooth_number < 30 else "lower",
                        "confidence": 1.0,
                        "vertices": state.vertices,
                        "faces": state.final_target_faces,
                        "movement": _movement(state.movement.movement),
                        "validationStatus": tooth_statuses.get(state.tooth_number, "pass"),
                        "validationMessage": tooth_messages.get(
                            state.tooth_number, "No geometric findings."
                        ),
                        "provenance": state.provenance.value,
                        "fixture": state.fixture,
                    }
                    for state in stage.tooth_states
                ],
                "validationStatus": stage_validation.status.value,
                "collisionCount": len(stage_validation.collision_results),
                "proximityCount": len(stage_validation.proximity_results),
                "contactCount": len(stage_validation.contact_results),
                "warnings": [*stage_validation.warnings, *stage_validation.errors],
                "provenance": stage.provenance.value,
                "fixture": stage.fixture,
            }
        )
    return {
        "stages": stages,
        "provenance": session.proposal.provenance.value,
        "fixture": session.proposal.fixture,
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
                "status": item.status.value,
                "warning": "; ".join(warning.message for warning in item.warnings),
                "fixture": item.fixture,
            }
            for item in session.adjuncts.attachments.sites
        ],
    }


def manifest_header(package: TreatmentExportPackage) -> str:
    return json.dumps(json.loads(package.manifest_path.read_text()), separators=(",", ":"))


def _movement(movement: ToothMovement) -> dict[str, float]:
    return {
        "translationX": movement.translation_x,
        "translationY": movement.translation_y,
        "translationZ": movement.translation_z,
        "rotation": movement.rotation,
        "tip": movement.tip,
        "torque": movement.torque,
        "intrusion": movement.intrusion,
        "extrusion": movement.extrusion,
    }


treatment_sessions = TreatmentSessionStore()
