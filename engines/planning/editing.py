"""Doctor movement editing and explicit restaging application layer."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone

from domain.case.provenance import DataProvenance
from domain.treatment_plan.setup import (
    DoctorMovementEdit,
    ProposalKind,
    ToothMovement,
    TreatmentPlanProposal,
)
from domain.treatment_plan.staging import StagingConfiguration, StagingResult
from domain.treatment_plan.validation import TreatmentValidationReport
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.staging_engine import TreatmentStagingEngine, resolve_dynamic_stage_count
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)


class TreatmentEditingError(ValueError):
    """Raised when a doctor edit cannot be applied safely."""


@dataclass(frozen=True)
class RecalculatedTreatmentPlan:
    """The complete output of edit → restage → geometric validation."""

    proposal: TreatmentPlanProposal
    staging: StagingResult
    validation: TreatmentValidationReport
    recalculation_id: str


@dataclass(frozen=True)
class TreatmentEditingApplication:
    """Applies explicit movement edits without mutating proposals or source meshes."""

    planner: TreatmentPlanningEngine = TreatmentPlanningEngine()
    staging_engine: TreatmentStagingEngine = TreatmentStagingEngine()
    validation_engine: GeometricValidationEngine = GeometricValidationEngine()

    def apply_edit(
        self,
        proposal: TreatmentPlanProposal,
        tooth_number: int | str,
        new_movement: ToothMovement,
        *,
        timestamp: str | None = None,
        reason: str = "doctor_edit",
    ) -> TreatmentPlanProposal:
        self._validate_movement(new_movement)
        current = self._movement_for(proposal, tooth_number)
        if (
            reason not in ("doctor_reset", "reset", "system_restore")
            and current.locked
            and new_movement.locked
            and not current.pose_equal(new_movement)
        ):
            raise TreatmentEditingError(
                f"Tooth {tooth_number} is locked; unlock before changing movement"
            )
        if (
            reason not in ("doctor_reset", "reset", "system_restore")
            and current.excluded
            and new_movement.excluded
            and not current.pose_equal(new_movement)
        ):
            raise TreatmentEditingError(
                f"Tooth {tooth_number} is excluded; include before changing movement"
            )
        # Normalize reset alias into persisted provenance vocabulary.
        if reason == "reset":
            reason = "doctor_reset"
        timestamp_value = timestamp or datetime.now(timezone.utc).isoformat()
        edit_seed = json.dumps(
            {
                "proposal_version": proposal.version_id,
                "tooth_number": tooth_number,
                "previous": current.__dict__,
                "new": new_movement.__dict__,
                "timestamp": timestamp_value,
                "reason": reason,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        edit_id = hashlib.sha256(edit_seed.encode()).hexdigest()
        edit = DoctorMovementEdit(
            edit_id=edit_id,
            tooth_number=tooth_number,
            previous_movement=current,
            new_movement=new_movement,
            timestamp=timestamp_value,
            version_id=hashlib.sha256((edit_seed + ":edit").encode()).hexdigest(),
            provenance=DataProvenance.GENERATED,
            reason=reason,
        )
        overrides = {tooth_number: new_movement}
        return self.planner.rebuild_proposal(
            proposal,
            overrides,
            proposal.edit_history + (edit,),
            ProposalKind.DOCTOR_EDITED,
        )

    def cancel(self, original_proposal: TreatmentPlanProposal) -> TreatmentPlanProposal:
        """Discard an uncommitted draft by returning the immutable original."""
        return original_proposal

    def reset_tooth(
        self,
        proposal: TreatmentPlanProposal,
        tooth_number: int | str,
        *,
        timestamp: str | None = None,
    ) -> TreatmentPlanProposal:
        original = self._original_movement(proposal, tooth_number)
        return self.apply_edit(
            proposal,
            tooth_number,
            original,
            timestamp=timestamp,
            reason="doctor_reset",
        )

    def reset_all(
        self,
        proposal: TreatmentPlanProposal,
        *,
        timestamp: str | None = None,
    ) -> TreatmentPlanProposal:
        if proposal.setup is None:
            raise TreatmentEditingError("Cannot reset a proposal without a setup")
        edited = proposal
        for state in proposal.setup.target_states:
            if proposal.planning_mode == "semantic_only_experimental":
                key = state.tooth_ref
            else:
                key = state.tooth_number if state.tooth_number is not None else state.tooth_ref
            if key is None:
                continue
            edited = self.reset_tooth(edited, key, timestamp=timestamp)
        return edited

    def recalculate(
        self,
        edited_proposal: TreatmentPlanProposal,
        staging_configuration: StagingConfiguration,
        validation_configuration: GeometricValidationConfiguration,
    ) -> RecalculatedTreatmentPlan:
        if edited_proposal.setup is None:
            raise TreatmentEditingError("Cannot recalculate a proposal without a setup")
        dynamic_count = resolve_dynamic_stage_count(
            edited_proposal,
            base_count=staging_configuration.stage_count,
            mode=staging_configuration.mode,
        )
        configuration = StagingConfiguration(
            stage_count=dynamic_count,
            mode=staging_configuration.mode,
            movement_limits=staging_configuration.movement_limits,
            engine_version=staging_configuration.engine_version,
        )
        recalculated = self.planner.rebuild_proposal(
            edited_proposal,
            {},
            edited_proposal.edit_history,
            ProposalKind.RECALCULATED,
        )
        staging = self.staging_engine.generate(recalculated, configuration)
        if staging.limitations:
            raise TreatmentEditingError("Restaging unavailable: " + "; ".join(staging.limitations))
        validation = self.validation_engine.validate(staging, validation_configuration)
        recalculation_id = hashlib.sha256(
            f"{recalculated.plan_id}:{staging.staging_id}:{validation.report_id}".encode()
        ).hexdigest()
        return RecalculatedTreatmentPlan(recalculated, staging, validation, recalculation_id)

    def apply_edit_and_recalculate(
        self,
        proposal: TreatmentPlanProposal,
        tooth_number: int | str,
        new_movement: ToothMovement,
        staging_configuration: StagingConfiguration,
        validation_configuration: GeometricValidationConfiguration,
        *,
        timestamp: str | None = None,
        reason: str = "doctor_edit",
    ) -> RecalculatedTreatmentPlan:
        """P4 flow: Doctor Edit → Target Update → Staging Rebuild → Validation."""
        edited = self.apply_edit(
            proposal, tooth_number, new_movement, timestamp=timestamp, reason=reason
        )
        return self.recalculate(edited, staging_configuration, validation_configuration)

    @staticmethod
    def _movement_for(proposal: TreatmentPlanProposal, tooth_number: int | str) -> ToothMovement:
        if proposal.setup is None:
            raise TreatmentEditingError("Proposal has no editable setup")
        for state in proposal.setup.target_states:
            if state.tooth_number == tooth_number or state.tooth_ref == tooth_number:
                return state.movement
        raise TreatmentEditingError(f"Tooth {tooth_number} is not editable in this proposal")

    @staticmethod
    def _original_movement(
        proposal: TreatmentPlanProposal, tooth_number: int | str
    ) -> ToothMovement:
        edits = [edit for edit in proposal.edit_history if edit.tooth_number == tooth_number]
        if edits:
            return edits[0].previous_movement
        return TreatmentEditingApplication._movement_for(proposal, tooth_number)

    @staticmethod
    def _validate_movement(movement: ToothMovement) -> None:
        if not all(
            math.isfinite(value)
            for value in (
                movement.translation_x,
                movement.translation_y,
                movement.translation_z,
                movement.rotation,
                movement.tip,
                movement.torque,
                movement.angulation,
                movement.intrusion,
                movement.extrusion,
            )
        ):
            raise TreatmentEditingError("Movement values must be finite numbers")
