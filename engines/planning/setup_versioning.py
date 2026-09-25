"""WP-05 Treatment Setup 2.0 — version lineage + source/current/target builders.

Extends P4 proposals; does not replace GeometricValidationEngine or staging.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from domain.movement.interaction import (
    ConstraintAvailability,
    CoordinateSpace,
)
from domain.treatment_plan.setup import ToothMovement, TreatmentPlanProposal
from domain.treatment_plan.setup_v2 import (
    ReadinessState,
    SetupComparisonResult,
    SetupToothDelta,
    ToothTargetState,
    TreatmentSetupReadiness,
    TreatmentSetupVersionMeta,
    count_moved_teeth,
    identity_transform,
    movement_to_transform,
    stable_setup_plan_id,
)
from domain.treatment_plan.staging import StagingResult
from domain.treatment_plan.validation import TreatmentValidationReport
from engines.planning.interaction_engine import constraint_availability_for_proposal


@dataclass(frozen=True)
class TreatmentSetupVersionSnapshot:
    """Immutable saved setup version (full proposal + validation snapshot)."""

    meta: TreatmentSetupVersionMeta
    proposal: TreatmentPlanProposal
    staging: StagingResult
    validation: TreatmentValidationReport


def build_version_meta(
    *,
    proposal: TreatmentPlanProposal,
    parent_version_id: str | None,
    validation: TreatmentValidationReport | None,
    description: str,
    author_source: str,
    created_at: str | None = None,
) -> TreatmentSetupVersionMeta:
    created = created_at or datetime.now(timezone.utc).isoformat()
    moved = count_moved_teeth(proposal)
    status = validation.status.value if validation is not None else None
    change_summary = description.strip() or (
        f"{proposal.proposal_kind.value}; {moved} tooth target(s) with non-identity transform"
    )
    return TreatmentSetupVersionMeta(
        version_id=proposal.version_id,
        parent_version_id=parent_version_id,
        plan_id=proposal.plan_id,
        setup_plan_id=stable_setup_plan_id(proposal.case_id),
        created_at=created,
        author_source=author_source,
        description=change_summary,
        proposal_kind=proposal.proposal_kind.value,
        moved_tooth_count=moved,
        validation_status=status,
        change_summary=change_summary,
    )


def snapshot_from_session_parts(
    *,
    proposal: TreatmentPlanProposal,
    staging: StagingResult,
    validation: TreatmentValidationReport,
    parent_version_id: str | None,
    description: str,
    author_source: str = "doctor",
    created_at: str | None = None,
) -> TreatmentSetupVersionSnapshot:
    meta = build_version_meta(
        proposal=proposal,
        parent_version_id=parent_version_id,
        validation=validation,
        description=description,
        author_source=author_source,
        created_at=created_at,
    )
    return TreatmentSetupVersionSnapshot(
        meta=meta,
        proposal=proposal,
        staging=staging,
        validation=validation,
    )


def find_version(
    history: tuple[TreatmentSetupVersionSnapshot, ...],
    version_id: str,
) -> TreatmentSetupVersionSnapshot | None:
    for item in history:
        if item.meta.version_id == version_id:
            return item
    return None


def append_immutable_version(
    history: tuple[TreatmentSetupVersionSnapshot, ...],
    snapshot: TreatmentSetupVersionSnapshot,
) -> tuple[TreatmentSetupVersionSnapshot, ...]:
    """Append a new immutable snapshot. Existing entries are never mutated."""
    if find_version(history, snapshot.meta.version_id) is not None:
        return history
    return history + (snapshot,)


def compare_proposals(
    left: TreatmentPlanProposal,
    right: TreatmentPlanProposal,
    *,
    left_version_id: str,
    right_version_id: str,
    left_validation_status: str | None = None,
    right_validation_status: str | None = None,
) -> SetupComparisonResult:
    left_map = _movement_map(left)
    right_map = _movement_map(right)
    keys = sorted(set(left_map) | set(right_map), key=str)
    changed: list[SetupToothDelta] = []
    unchanged = 0
    for key in keys:
        left_m = left_map.get(key, ToothMovement())
        right_m = right_map.get(key, ToothMovement())
        tooth_ref, arch = _identity_for(left, right, key)
        if left_m.pose_equal(right_m):
            unchanged += 1
            continue
        changed.append(
            SetupToothDelta(
                tooth_key=str(key),
                tooth_ref=tooth_ref,
                arch=arch,
                translation_delta=(
                    right_m.translation_x - left_m.translation_x,
                    right_m.translation_y - left_m.translation_y,
                    right_m.translation_z - left_m.translation_z,
                ),
                rotation_delta=(
                    right_m.rotation - left_m.rotation,
                    right_m.tip - left_m.tip,
                    right_m.torque - left_m.torque,
                ),
                changed=True,
            )
        )
    notes = (
        "Comparison is geometric/transform-only.",
        "No clinical ranking or optimality claim is assigned.",
    )
    return SetupComparisonResult(
        left_version_id=left_version_id,
        right_version_id=right_version_id,
        changed_teeth=tuple(changed),
        unchanged_count=unchanged,
        left_validation_status=left_validation_status,
        right_validation_status=right_validation_status,
        notes=notes,
    )


def build_tooth_target_states(
    *,
    case_id: str,
    proposal: TreatmentPlanProposal,
    constraint_availability: ConstraintAvailability,
    validation_by_tooth: dict[str | int, str] | None = None,
) -> tuple[ToothTargetState, ...]:
    """SOURCE = identity; CURRENT = SOURCE for FV; TARGET = doctor/planner transforms."""
    if proposal.setup is None:
        return ()
    validation_by_tooth = validation_by_tooth or {}
    states: list[ToothTargetState] = []
    for target in proposal.setup.target_states:
        tooth_key = target.tooth_ref or (
            str(target.tooth_number) if target.tooth_number is not None else ""
        )
        if not tooth_key:
            continue
        limitations: list[str] = [
            "Current patient layer equals source until a progress scan exists.",
            "Target edit is not clinical approval.",
        ]
        if target.planning_mode == "semantic_only_experimental":
            limitations.append("Semantic-only identity; FDI not fabricated.")
        if constraint_availability in (
            ConstraintAvailability.UNAVAILABLE,
            ConstraintAvailability.NOT_CONFIGURED,
        ):
            limitations.append("Movement constraints unavailable.")
        coord = CoordinateSpace.WORLD
        semantics = getattr(target.coordinate_system, "semantics", ()) or ()
        if any("engineering" in str(item).lower() for item in semantics):
            coord = CoordinateSpace.ENGINEERING_LOCAL
        source_tf = identity_transform()
        fdi_number = None
        if (
            proposal.planning_mode != "semantic_only_experimental"
            and isinstance(target.tooth_number, int)
        ):
            fdi_number = target.tooth_number
        states.append(
            ToothTargetState(
                case_id=case_id,
                tooth_ref=target.tooth_ref,
                tooth_key=tooth_key,
                semantic_label=target.semantic_label,
                fdi_number=fdi_number,
                arch=target.arch,
                source_mesh_sha256=None,
                source_transform=source_tf,
                current_transform=source_tf,
                target_transform=movement_to_transform(target.movement),
                coordinate_space=coord,
                locked=target.movement.locked,
                excluded=target.movement.excluded,
                constraint_availability=constraint_availability,
                validation_status=validation_by_tooth.get(tooth_key)
                or validation_by_tooth.get(target.tooth_number or ""),
                limitations=tuple(limitations),
            )
        )
    return tuple(states)


def build_setup_readiness(
    *,
    proposal: TreatmentPlanProposal,
    staging: StagingResult,
    validation: TreatmentValidationReport | None,
    has_real_geometry: bool,
    constraint_availability: ConstraintAvailability,
    occlusion_readiness: ReadinessState | None = None,
    clinical_axes_readiness: ReadinessState | None = None,
) -> TreatmentSetupReadiness:
    arches = {
        state.arch
        for state in (proposal.setup.target_states if proposal.setup else ())
        if state.arch
    }
    has_both_arches = "upper" in arches and "lower" in arches
    has_identity = bool(
        proposal.setup
        and any(
            state.tooth_ref or state.tooth_number is not None
            for state in proposal.setup.target_states
        )
    )
    notes = (
        "Readiness signals are capability gates, not an AI score.",
        "Target transforms never unlock staging, IPR, attachments, occlusion, or production CAD.",
        "Doctor edits are not clinical approval.",
        "Occlusion/clinical-axes readiness reflects WP-08 capability state when evidence exists.",
    )
    return TreatmentSetupReadiness(
        real_geometry=ReadinessState.AVAILABLE
        if has_real_geometry
        else ReadinessState.NOT_AVAILABLE,
        identity=ReadinessState.REQUIRES_REVIEW
        if has_identity
        else ReadinessState.NOT_AVAILABLE,
        arch=ReadinessState.AVAILABLE
        if has_both_arches
        else (ReadinessState.REQUIRES_REVIEW if arches else ReadinessState.NOT_AVAILABLE),
        transform=ReadinessState.AVAILABLE
        if proposal.setup is not None
        else ReadinessState.NOT_AVAILABLE,
        constraint=(
            ReadinessState.AVAILABLE
            if constraint_availability is ConstraintAvailability.CONFIGURED
            else ReadinessState.UNAVAILABLE
        ),
        validation=ReadinessState.AVAILABLE
        if validation is not None and staging.stages
        else ReadinessState.UNAVAILABLE,
        occlusion=occlusion_readiness or ReadinessState.NOT_AVAILABLE,
        clinical_axes=clinical_axes_readiness or ReadinessState.NOT_AVAILABLE,
        notes=notes,
    )


def build_treatment_setup_payload(
    *,
    case_id: str,
    proposal: TreatmentPlanProposal,
    staging: StagingResult,
    validation: TreatmentValidationReport,
    parent_version_id: str | None,
    version_history: tuple[TreatmentSetupVersionSnapshot, ...],
    source_kind: str,
    occlusion_readiness: ReadinessState | None = None,
    clinical_axes_readiness: ReadinessState | None = None,
) -> dict[str, Any]:
    constraint = constraint_availability_for_proposal(proposal, staging)
    has_real = True
    if proposal.fixture and "fixture" in source_kind:
        has_real = False
    elif source_kind in (
        "validated_real_case",
        "real_case",
        "pipeline",
        "segmentation",
        "test_fixture",
    ):
        # test_fixture uses genuine persisted artifact geometry (WP-01 path).
        has_real = source_kind != "development_treatment_fixture"

    tooth_states = build_tooth_target_states(
        case_id=case_id,
        proposal=proposal,
        constraint_availability=constraint,
    )
    readiness = build_setup_readiness(
        proposal=proposal,
        staging=staging,
        validation=validation,
        has_real_geometry=has_real,
        constraint_availability=constraint,
        occlusion_readiness=occlusion_readiness,
        clinical_axes_readiness=clinical_axes_readiness,
    )
    current_vs_target = compare_proposals(
        _identity_proposal_view(proposal),
        proposal,
        left_version_id="current",
        right_version_id="target",
        left_validation_status=None,
        right_validation_status=validation.status.value,
    )
    return {
        "contract_version": "treatment_setup_2.0",
        "setup_plan_id": stable_setup_plan_id(case_id),
        "plan_id": proposal.plan_id,
        "version_id": proposal.version_id,
        "parent_version_id": parent_version_id,
        "proposal_kind": proposal.proposal_kind.value,
        "layers": {
            "source": "Immutable processed source geometry (never mutated).",
            "current": "Current patient layer; equals source until progress scans exist.",
            "target": "Doctor/planner target transforms over source geometry.",
        },
        "teeth": [state.payload() for state in tooth_states],
        "moved_tooth_count": count_moved_teeth(proposal),
        "readiness": readiness.payload(),
        "constraint_availability": constraint.value,
        "current_vs_target": current_vs_target.payload(),
        "versions": [item.meta.payload() for item in version_history],
        "clinically_approved": False,
        "notes": [
            "Treatment Setup 2.0 does not claim clinical optimality.",
            "Geometric executability is not clinical clearance.",
            "Occlusion/clinical-axes readiness is consumed from WP-08 when evidence exists.",
        ],
    }


def _movement_map(proposal: TreatmentPlanProposal) -> dict[str | int, ToothMovement]:
    if proposal.setup is None:
        return {}
    result: dict[str | int, ToothMovement] = {}
    for state in proposal.setup.target_states:
        if state.tooth_ref:
            key: str | int = state.tooth_ref
        elif state.tooth_number is not None:
            key = state.tooth_number
        else:
            continue
        result[key] = state.movement
    return result


def _identity_for(
    left: TreatmentPlanProposal,
    right: TreatmentPlanProposal,
    key: str | int,
) -> tuple[str | None, str | None]:
    for proposal in (left, right):
        if proposal.setup is None:
            continue
        for state in proposal.setup.target_states:
            state_key = state.tooth_ref or state.tooth_number
            if state_key == key:
                return state.tooth_ref, state.arch
    return (key if isinstance(key, str) else None), None


def _identity_proposal_view(proposal: TreatmentPlanProposal) -> TreatmentPlanProposal:
    if proposal.setup is None:
        return proposal
    identity_targets = tuple(
        replace(
            state,
            movement=ToothMovement(
                locked=state.movement.locked,
                excluded=state.movement.excluded,
            ),
        )
        for state in proposal.setup.target_states
    )
    return replace(proposal, setup=replace(proposal.setup, target_states=identity_targets))


__all__ = [
    "TreatmentSetupVersionSnapshot",
    "append_immutable_version",
    "build_setup_readiness",
    "build_tooth_target_states",
    "build_treatment_setup_payload",
    "build_version_meta",
    "compare_proposals",
    "find_version",
    "snapshot_from_session_parts",
]
