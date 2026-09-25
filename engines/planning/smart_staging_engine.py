"""WP-06 Smart Staging Engine — deterministic staging bound to Treatment Setup versions.

Reuses ``TreatmentStagingEngine`` linear interpolation. Does not invent clinical limits,
IPR, attachments, occlusion, or clinical approval.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from domain.movement.interaction import ConstraintAvailability
from domain.treatment_plan.setup import ToothMovement, TreatmentPlanProposal
from domain.treatment_plan.setup_v2 import stable_setup_plan_id
from domain.treatment_plan.smart_staging import (
    ALGORITHM_NAME,
    ALGORITHM_VERSION,
    TECHNICAL_NUMERICAL_TOLERANCE,
    SmartStagingVersionMeta,
    StagingFreshness,
    StagingReadiness,
    StagingReadinessState,
    StagingTruthState,
    stable_staging_plan_id,
)
from domain.treatment_plan.staging import StagingConfiguration, StagingResult
from domain.treatment_plan.validation import TreatmentValidationReport
from engines.planning.interaction_engine import constraint_availability_for_proposal
from engines.planning.staging_engine import (
    TreatmentStagingEngine,
    resolve_dynamic_stage_count,
)


@dataclass(frozen=True)
class SmartStagingPlan:
    """Persisted staging plan bound to a Treatment Setup version."""

    meta: SmartStagingVersionMeta
    staging: StagingResult
    final_equals_target: bool
    reconstruction_max_error: float
    readiness: StagingReadiness

    def payload(self) -> dict[str, Any]:
        return {
            "contract_version": "smart_staging_1.0",
            "meta": self.meta.payload(),
            "staging_id": self.staging.staging_id,
            "stage_count": self.staging.stage_count,
            "final_equals_target": self.final_equals_target,
            "reconstruction_max_error": self.reconstruction_max_error,
            "technical_numerical_tolerance": TECHNICAL_NUMERICAL_TOLERANCE,
            "readiness": self.readiness.payload(),
            "assumptions": list(self.staging.assumptions),
            "warnings": list(self.staging.warnings),
            "limitations": list(self.staging.limitations) + list(self.meta.limitations),
            "clinically_approved": False,
            "clinically_optimal": False,
            "notes": [
                "Computational staging proposal — not clinically optimized.",
                "Geometric validation execution is not clinical clearance.",
                "WP-07 and later packages are not started.",
            ],
        }


@dataclass(frozen=True)
class SmartStagingVersionSnapshot:
    plan: SmartStagingPlan
    validation: TreatmentValidationReport | None = None


def evaluate_freshness(
    *,
    source_setup_version_id: str | None,
    current_setup_version_id: str | None,
    has_staging: bool,
) -> StagingFreshness:
    if not has_staging or not source_setup_version_id or not current_setup_version_id:
        return StagingFreshness.UNAVAILABLE
    if source_setup_version_id == current_setup_version_id:
        return StagingFreshness.CURRENT
    return StagingFreshness.STALE


def final_stage_matches_target(
    proposal: TreatmentPlanProposal,
    staging: StagingResult,
    *,
    tolerance: float = TECHNICAL_NUMERICAL_TOLERANCE,
) -> tuple[bool, float]:
    """Verify final-stage movements/vertices reproduce the setup target within technical tolerance."""
    if proposal.setup is None or not staging.stages:
        return False, float("inf")
    final = staging.final_stage
    target_by_key = {
        (state.tooth_ref or state.tooth_number): state for state in proposal.setup.target_states
    }
    max_error = 0.0
    for tooth in final.tooth_states:
        key = tooth.tooth_ref or tooth.tooth_number
        target = target_by_key.get(key)
        if target is None:
            return False, float("inf")
        # Vertices must be identical references or numerically equal (final copies target).
        if tooth.vertices is not target.target_vertices:
            if len(tooth.vertices) != len(target.target_vertices):
                return False, float("inf")
            for left, right in zip(tooth.vertices, target.target_vertices, strict=True):
                for a, b in zip(left, right, strict=True):
                    max_error = max(max_error, abs(a - b))
        movement_error = _movement_abs_diff(tooth.movement.movement, target.movement)
        max_error = max(max_error, movement_error)
    return max_error <= tolerance, max_error


def _movement_abs_diff(left: ToothMovement, right: ToothMovement) -> float:
    fields = (
        "translation_x",
        "translation_y",
        "translation_z",
        "rotation",
        "tip",
        "torque",
        "angulation",
        "intrusion",
        "extrusion",
    )
    return max(abs(getattr(left, field) - getattr(right, field)) for field in fields)


def build_staging_readiness(
    *,
    proposal: TreatmentPlanProposal,
    staging: StagingResult | None,
    validation: TreatmentValidationReport | None,
    constraint_availability: ConstraintAvailability,
    freshness: StagingFreshness,
    occlusion_readiness: StagingReadinessState | None = None,
    clinical_axes_readiness: StagingReadinessState | None = None,
) -> StagingReadiness:
    has_setup = proposal.setup is not None and bool(proposal.setup.target_states)
    has_stages = staging is not None and bool(staging.stages)
    notes = (
        "Readiness signals are capability gates, not an AI score.",
        "Staging never unlocks IPR, attachments, or production CAD.",
        "Doctor review is required for any generated staging proposal.",
        "Occlusion/clinical-axes readiness reflects WP-08 capability state when evidence exists.",
    )
    return StagingReadiness(
        target_setup_available=StagingReadinessState.AVAILABLE
        if has_setup
        else StagingReadinessState.NOT_AVAILABLE,
        target_version_valid=StagingReadinessState.AVAILABLE
        if proposal.version_id
        else StagingReadinessState.NOT_AVAILABLE,
        movement_data_available=StagingReadinessState.AVAILABLE
        if has_setup
        else StagingReadinessState.NOT_AVAILABLE,
        constraints=(
            StagingReadinessState.AVAILABLE
            if constraint_availability is ConstraintAvailability.CONFIGURED
            else StagingReadinessState.UNAVAILABLE
        ),
        validation=StagingReadinessState.AVAILABLE
        if validation is not None and has_stages
        else StagingReadinessState.UNAVAILABLE,
        occlusion=occlusion_readiness or StagingReadinessState.NOT_AVAILABLE,
        clinical_axes=clinical_axes_readiness or StagingReadinessState.NOT_AVAILABLE,
        staging_proposal_available=(
            StagingReadinessState.REQUIRES_REVIEW
            if has_stages and freshness is StagingFreshness.CURRENT
            else StagingReadinessState.UNAVAILABLE
            if freshness is StagingFreshness.STALE
            else (
                StagingReadinessState.AVAILABLE
                if has_stages
                else StagingReadinessState.NOT_AVAILABLE
            )
        ),
        doctor_review_required=True,
        notes=notes,
    )


def count_affected_teeth(proposal: TreatmentPlanProposal) -> int:
    if proposal.setup is None:
        return 0
    count = 0
    for state in proposal.setup.target_states:
        if state.movement.excluded:
            continue
        if state.movement.locked and state.movement.pose_equal(
            ToothMovement(locked=True, excluded=state.movement.excluded)
        ):
            continue
        if not state.movement.pose_equal(
            ToothMovement(locked=state.movement.locked, excluded=state.movement.excluded)
        ):
            count += 1
    return count


def with_freshness(plan: SmartStagingPlan, current_setup_version_id: str) -> SmartStagingPlan:
    freshness = evaluate_freshness(
        source_setup_version_id=plan.meta.source_setup_version_id,
        current_setup_version_id=current_setup_version_id,
        has_staging=bool(plan.staging.stages),
    )
    meta = replace(plan.meta, freshness=freshness)
    notes = plan.readiness.notes
    staging_available = plan.readiness.staging_proposal_available
    if freshness is StagingFreshness.STALE:
        staging_available = StagingReadinessState.UNAVAILABLE
        if "stale relative" not in " ".join(notes).lower():
            notes = notes + (
                "Staging is stale relative to the current Treatment Setup version.",
            )
    elif freshness is StagingFreshness.CURRENT and plan.staging.stages:
        staging_available = StagingReadinessState.REQUIRES_REVIEW
    readiness = replace(
        plan.readiness,
        staging_proposal_available=staging_available,
        doctor_review_required=True,
        notes=notes,
    )
    return replace(plan, meta=meta, readiness=readiness)


@dataclass(frozen=True)
class SmartStagingEngine:
    """Generate / wrap Phase-6 staging with WP-06 binding and honesty contracts."""

    stager: TreatmentStagingEngine = TreatmentStagingEngine()

    def wrap(
        self,
        proposal: TreatmentPlanProposal,
        staging: StagingResult,
        configuration: StagingConfiguration,
        *,
        validation: TreatmentValidationReport | None = None,
        parent_staging_version_id: str | None = None,
        author_source: str = "system",
        description: str = "",
        created_at: str | None = None,
    ) -> SmartStagingPlan:
        """Bind an already-generated Phase-6 staging result (no second interpolation)."""
        equals, max_error = final_stage_matches_target(proposal, staging)
        constraint = constraint_availability_for_proposal(proposal, staging)
        freshness = StagingFreshness.CURRENT if staging.stages else StagingFreshness.UNAVAILABLE
        limitations = [
            "Computational linear-progress staging proposal — not clinically optimized.",
            "No biological movement limits were invented.",
            "IPR and attachments are not generated by this engine.",
        ]
        if constraint in (
            ConstraintAvailability.UNAVAILABLE,
            ConstraintAvailability.NOT_CONFIGURED,
        ):
            limitations.append("Clinical movement constraints unavailable.")
        if not equals:
            limitations.append(
                "Final-stage reconstruction exceeded technical numerical tolerance."
            )
        truth = (
            StagingTruthState.REQUIRES_REVIEW
            if staging.stages
            else StagingTruthState.NOT_AVAILABLE
        )
        created = created_at or datetime.now(timezone.utc).isoformat()
        input_hash = hashlib.sha256(
            json.dumps(
                {
                    "setup_version_id": proposal.version_id,
                    "plan_id": proposal.plan_id,
                    "stage_count": configuration.stage_count,
                    "mode": configuration.mode,
                    "engine_version": configuration.engine_version,
                    "algorithm": ALGORITHM_NAME,
                    "algorithm_version": ALGORITHM_VERSION,
                    "staging_id": staging.staging_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        meta = SmartStagingVersionMeta(
            staging_plan_id=stable_staging_plan_id(proposal.case_id),
            staging_version_id=staging.staging_id,
            parent_staging_version_id=parent_staging_version_id,
            case_id=proposal.case_id,
            setup_plan_id=stable_setup_plan_id(proposal.case_id),
            source_setup_version_id=proposal.version_id,
            created_at=created,
            author_source=author_source,
            description=description
            or f"{ALGORITHM_NAME} @ {ALGORITHM_VERSION}; {staging.stage_count} stages",
            algorithm_name=ALGORITHM_NAME,
            algorithm_version=ALGORITHM_VERSION,
            configuration={
                "stage_count": staging.stage_count,
                "mode": configuration.mode,
                "engine_version": configuration.engine_version,
                "movement_limits_configured": configuration.movement_limits is not None,
            },
            input_hash=input_hash,
            stage_count=staging.stage_count,
            affected_tooth_count=count_affected_teeth(proposal),
            truth_state=truth,
            validation_status=validation.status.value if validation else None,
            freshness=freshness,
            limitations=tuple(limitations),
        )
        readiness = build_staging_readiness(
            proposal=proposal,
            staging=staging,
            validation=validation,
            constraint_availability=constraint,
            freshness=freshness,
        )
        return SmartStagingPlan(
            meta=meta,
            staging=staging,
            final_equals_target=equals,
            reconstruction_max_error=max_error if max_error != float("inf") else -1.0,
            readiness=readiness,
        )

    def generate(
        self,
        proposal: TreatmentPlanProposal,
        configuration: StagingConfiguration | None = None,
        *,
        validation: TreatmentValidationReport | None = None,
        parent_staging_version_id: str | None = None,
        author_source: str = "system",
        description: str = "",
        created_at: str | None = None,
    ) -> SmartStagingPlan:
        config = configuration or StagingConfiguration(
            stage_count=2,
            mode="macro",
            movement_limits=None,
            engine_version=ALGORITHM_VERSION,
        )
        dynamic_count = resolve_dynamic_stage_count(
            proposal, base_count=config.stage_count, mode=config.mode
        )
        config = replace(
            config,
            stage_count=dynamic_count,
            engine_version=config.engine_version or ALGORITHM_VERSION,
        )
        staging = self.stager.generate(proposal, config)
        return self.wrap(
            proposal,
            staging,
            config,
            validation=validation,
            parent_staging_version_id=parent_staging_version_id,
            author_source=author_source,
            description=description,
            created_at=created_at,
        )

    def with_freshness(
        self, plan: SmartStagingPlan, current_setup_version_id: str
    ) -> SmartStagingPlan:
        return with_freshness(plan, current_setup_version_id)


def append_staging_version(
    history: tuple[SmartStagingVersionSnapshot, ...],
    snapshot: SmartStagingVersionSnapshot,
) -> tuple[SmartStagingVersionSnapshot, ...]:
    for item in history:
        if item.plan.meta.staging_version_id == snapshot.plan.meta.staging_version_id:
            return history
    return history + (snapshot,)


def find_staging_version(
    history: tuple[SmartStagingVersionSnapshot, ...],
    staging_version_id: str,
) -> SmartStagingVersionSnapshot | None:
    for item in history:
        if item.plan.meta.staging_version_id == staging_version_id:
            return item
    return None


def build_smart_staging_review_payload(
    plan: SmartStagingPlan | None,
    *,
    current_setup_version_id: str | None,
    staging_history: tuple[SmartStagingVersionSnapshot, ...] = (),
) -> dict[str, Any]:
    if plan is None:
        return {
            "contract_version": "smart_staging_1.0",
            "freshness": StagingFreshness.UNAVAILABLE.value,
            "clinically_approved": False,
            "clinically_optimal": False,
            "versions": [],
            "notes": ["Smart staging plan unavailable."],
        }
    viewed = (
        with_freshness(plan, current_setup_version_id)
        if current_setup_version_id
        else plan
    )
    payload = viewed.payload()
    payload["versions"] = [item.plan.meta.payload() for item in staging_history]
    return payload


__all__ = [
    "SmartStagingEngine",
    "SmartStagingPlan",
    "SmartStagingVersionSnapshot",
    "append_staging_version",
    "build_smart_staging_review_payload",
    "build_staging_readiness",
    "count_affected_teeth",
    "evaluate_freshness",
    "final_stage_matches_target",
    "find_staging_version",
]
