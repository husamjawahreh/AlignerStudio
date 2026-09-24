"""P6 advanced planning intelligence — AI proposes, geometry validates, doctor decides."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace

from adapters.sttalign import STTAlignAdapter, STTAlignUnavailableError
from adapters.tadpm import TADPMAdapter, TADPMUnavailableError
from adapters.threedteethsam import TeethSAMAdapter, TeethSAMUnavailableError
from domain.case.provenance import DataProvenance
from domain.treatment_plan.intelligence import (
    DecisionState,
    IntelligenceCapabilityStatus,
    ModelOutputContract,
    PlanningIntelligenceReport,
    ResearchAdapterEvaluation,
    SetupAlternativeSummary,
)
from domain.treatment_plan.setup import ProposalKind, ToothMovement, TreatmentPlanProposal
from domain.treatment_plan.staging import StagingConfiguration, StagingResult
from domain.treatment_plan.validation import TreatmentValidationReport, ValidationStatus
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.staging_engine import TreatmentStagingEngine
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)

ENGINE_NAME = "alignerstudio-deterministic-intelligence"
ENGINE_VERSION = "p6-1.0.0"


@dataclass(frozen=True)
class IntelligenceCandidate:
    """In-session candidate with full geometry for doctor acceptance."""

    summary: SetupAlternativeSummary
    proposal: TreatmentPlanProposal
    staging: StagingResult
    validation: TreatmentValidationReport


@dataclass
class AdvancedPlanningIntelligenceResult:
    report: PlanningIntelligenceReport
    candidates: tuple[IntelligenceCandidate, ...]


def research_adapter_evaluations() -> tuple[ResearchAdapterEvaluation, ...]:
    """Record honest evaluations — no silent substitution of unsupported models."""
    stt_status = IntelligenceCapabilityStatus.UNAVAILABLE
    tadpm_status = IntelligenceCapabilityStatus.UNAVAILABLE
    sam_status = IntelligenceCapabilityStatus.UNAVAILABLE
    try:
        STTAlignAdapter().propose_alignment()
    except STTAlignUnavailableError:
        stt_status = IntelligenceCapabilityStatus.UNAVAILABLE
    try:
        TADPMAdapter().propose_arrangement()
    except TADPMUnavailableError:
        tadpm_status = IntelligenceCapabilityStatus.UNAVAILABLE
    try:
        TeethSAMAdapter().propose_plan()
    except TeethSAMUnavailableError:
        sam_status = IntelligenceCapabilityStatus.UNAVAILABLE

    return (
        ResearchAdapterEvaluation(
            adapter_id="sttalign",
            model_name="STTAlign",
            product_problem=(
                "Occlusion-aware / collision-aware tooth alignment proposals from research models."
            ),
            decision="REFERENCE ONLY — adapter boundary only",
            status=stt_status,
            model_version=None,
            provenance_notes=(
                "No verified checkpoint or Aligner Studio real-case benchmark in-repo."
            ),
            benchmark_status="not_run",
            limitations=(
                "Older CUDA/PyTorch/PyTorch3D dependency stack.",
                "No measured comparison against deterministic GeometricValidationEngine.",
                "Must not bypass validation if later enabled.",
            ),
            compared_to_deterministic_validation="not_compared — model unavailable",
        ),
        ResearchAdapterEvaluation(
            adapter_id="tadpm",
            model_name="TADPM",
            product_problem="Automatic tooth arrangement / diffusion-based planning candidates.",
            decision="REFERENCE ONLY — adapter boundary only",
            status=tadpm_status,
            model_version=None,
            provenance_notes=(
                "No verified checkpoint or Aligner Studio real-case benchmark in-repo."
            ),
            benchmark_status="not_run",
            limitations=(
                "Specialized CUDA-dependent environment.",
                "No measured comparison against deterministic GeometricValidationEngine.",
                "Must not bypass validation if later enabled.",
            ),
            compared_to_deterministic_validation="not_compared — model unavailable",
        ),
        ResearchAdapterEvaluation(
            adapter_id="3dteethsam",
            model_name="3DTeethSAM",
            product_problem="Tooth instance segmentation (not treatment planning).",
            decision="BENCHMARK CANDIDATE for segmentation — not a planning adapter",
            status=sam_status,
            model_version=None,
            provenance_notes=(
                "Segmentation research candidate; must not replace ToothInstanceNet "
                "without measured evidence."
            ),
            benchmark_status="blocked",
            limitations=(
                "Not a planning/arrangement model.",
                "Heavy SAM2/PyTorch3D stack; host benchmark previously blocked.",
                "Irrelevant to generate treatment targets.",
            ),
            compared_to_deterministic_validation=(
                "not_applicable — segmentation model, not planning"
            ),
        ),
    )


class AdvancedPlanningIntelligenceEngine:
    """Generate validated setup/staging candidates without inventing clinical data."""

    def __init__(
        self,
        *,
        planner: TreatmentPlanningEngine | None = None,
        stager: TreatmentStagingEngine | None = None,
        validator: GeometricValidationEngine | None = None,
        validation_config: GeometricValidationConfiguration | None = None,
    ) -> None:
        self._planner = planner or TreatmentPlanningEngine()
        self._stager = stager or TreatmentStagingEngine()
        self._validator = validator or GeometricValidationEngine()
        self._validation_config = validation_config or GeometricValidationConfiguration(
            1.0, 0.001, 0.0
        )

    def generate(
        self,
        proposal: TreatmentPlanProposal,
        staging: StagingResult,
        validation: TreatmentValidationReport,
        *,
        staging_configuration: StagingConfiguration | None = None,
        generate_alternatives: bool = True,
    ) -> AdvancedPlanningIntelligenceResult:
        """Propose alternatives; every candidate is staged and geometrically validated.

        When ``generate_alternatives`` is False, only the active baseline is wrapped
        (no extra restage/validate). Used on the hot compose path for large real cases.
        """
        if proposal.setup is None or not staging.stages:
            report = PlanningIntelligenceReport(
                landmark_assisted_target_setup=IntelligenceCapabilityStatus.UNAVAILABLE,
                arch_form_aware_planning=IntelligenceCapabilityStatus.UNAVAILABLE,
                occlusion_aware_planning=IntelligenceCapabilityStatus.UNAVAILABLE,
                collision_aware_candidate_generation=IntelligenceCapabilityStatus.UNAVAILABLE,
                constrained_six_dof_trajectories=IntelligenceCapabilityStatus.UNAVAILABLE,
                staging_proposals=IntelligenceCapabilityStatus.UNAVAILABLE,
                alternative_setups=IntelligenceCapabilityStatus.UNAVAILABLE,
                alternatives=(),
                research_adapters=research_adapter_evaluations(),
                notes=(
                    "Advanced planning intelligence unavailable: no treatment setup/stages.",
                ),
            )
            return AdvancedPlanningIntelligenceResult(report=report, candidates=())

        base_config = staging_configuration or StagingConfiguration(
            stage_count=max(2, len(staging.stages)),
            mode="macro",
        )
        landmarks_ok = all(
            state.coordinate_system is not None for state in proposal.setup.target_states
        )
        arch_form_ok = len(proposal.setup.target_states) >= 3
        limits_configured = any(
            state.movement.limit_status != "not_configured"
            for stage in staging.stages
            for state in stage.tooth_states
        )

        candidates: list[IntelligenceCandidate] = []

        candidates.append(
            self._candidate(
                proposal,
                staging,
                validation,
                strategy="baseline",
                label="Current deterministic setup",
                model_name=ENGINE_NAME,
                limitations=(
                    "Baseline proposal from deterministic TreatmentPlanningEngine.",
                    "Not a learned model output.",
                ),
                is_active=True,
            )
        )

        if generate_alternatives:
            candidates.extend(
                self._build_assisted_candidates(
                    proposal,
                    base_config,
                    landmarks_ok=landmarks_ok,
                    arch_form_ok=arch_form_ok,
                )
            )

        notes = [
            "AI proposes. Deterministic geometry validates. Doctor decides.",
            "Research models STTAlign/TADPM/3DTeethSAM remain Unavailable.",
            "No fabricated confidence or clinical claims.",
        ]
        if not generate_alternatives:
            notes.append(
                "Assisted alternatives not expanded on this path; request planning "
                "intelligence to generate validated candidates."
            )
        if not limits_configured:
            notes.append(
                "Constrained 6-DOF trajectories unavailable: no movement limits configured."
            )
        notes.append("Occlusion-aware planning unavailable: no bite/registration evidence.")

        alternatives_status = (
            IntelligenceCapabilityStatus.COMPUTED
            if generate_alternatives and len(candidates) > 1
            else (
                IntelligenceCapabilityStatus.BOUNDARY_ONLY
                if not generate_alternatives
                else IntelligenceCapabilityStatus.COMPUTED
            )
        )

        report = PlanningIntelligenceReport(
            landmark_assisted_target_setup=(
                IntelligenceCapabilityStatus.COMPUTED
                if landmarks_ok and generate_alternatives
                else (
                    IntelligenceCapabilityStatus.BOUNDARY_ONLY
                    if landmarks_ok
                    else IntelligenceCapabilityStatus.UNAVAILABLE
                )
            ),
            arch_form_aware_planning=(
                IntelligenceCapabilityStatus.COMPUTED
                if arch_form_ok and generate_alternatives
                else (
                    IntelligenceCapabilityStatus.BOUNDARY_ONLY
                    if arch_form_ok
                    else IntelligenceCapabilityStatus.UNAVAILABLE
                )
            ),
            occlusion_aware_planning=IntelligenceCapabilityStatus.UNAVAILABLE,
            collision_aware_candidate_generation=(
                IntelligenceCapabilityStatus.COMPUTED
                if generate_alternatives
                else IntelligenceCapabilityStatus.BOUNDARY_ONLY
            ),
            constrained_six_dof_trajectories=(
                IntelligenceCapabilityStatus.COMPUTED
                if limits_configured
                else IntelligenceCapabilityStatus.UNAVAILABLE
            ),
            staging_proposals=(
                IntelligenceCapabilityStatus.COMPUTED
                if generate_alternatives
                else IntelligenceCapabilityStatus.BOUNDARY_ONLY
            ),
            alternative_setups=alternatives_status,
            alternatives=tuple(item.summary for item in candidates),
            research_adapters=research_adapter_evaluations(),
            notes=tuple(notes),
        )
        return AdvancedPlanningIntelligenceResult(
            report=report, candidates=tuple(candidates)
        )

    def _build_assisted_candidates(
        self,
        proposal: TreatmentPlanProposal,
        base_config: StagingConfiguration,
        *,
        landmarks_ok: bool,
        arch_form_ok: bool,
    ) -> list[IntelligenceCandidate]:
        candidates: list[IntelligenceCandidate] = []
        if landmarks_ok:
            landmark_proposal = self._rebuild_scaled(proposal, 1.0, tag="landmark")
            landmark_staging = self._stager.generate(landmark_proposal, base_config)
            landmark_validation = self._validator.validate(
                landmark_staging, self._validation_config
            )
            candidates.append(
                self._candidate(
                    landmark_proposal,
                    landmark_staging,
                    landmark_validation,
                    strategy="landmark_assisted",
                    label="Landmark-assisted local-frame setup",
                    model_name=ENGINE_NAME,
                    limitations=(
                        "Uses existing tooth local frames / landmarks only.",
                        "Does not invent landmarks or FDI identities.",
                        "Confidence is not fabricated.",
                    ),
                    is_active=False,
                )
            )

        if arch_form_ok:
            arch_proposal = self._rebuild_scaled(
                proposal, 1.0, tag="arch", lateral_scale=0.85, anterior_scale=1.0
            )
            arch_staging = self._stager.generate(arch_proposal, base_config)
            arch_validation = self._validator.validate(arch_staging, self._validation_config)
            candidates.append(
                self._candidate(
                    arch_proposal,
                    arch_staging,
                    arch_validation,
                    strategy="arch_form_aware",
                    label="Arch-form-aware dampened lateral movement",
                    model_name=ENGINE_NAME,
                    limitations=(
                        "Geometric lateral dampening only; not a clinical arch-form goal.",
                        "Requires doctor review before acceptance.",
                    ),
                    is_active=False,
                )
            )

        reduced_proposal = self._rebuild_scaled(proposal, 0.75, tag="collision")
        reduced_staging = self._stager.generate(reduced_proposal, base_config)
        reduced_validation = self._validator.validate(reduced_staging, self._validation_config)
        candidates.append(
            self._candidate(
                reduced_proposal,
                reduced_staging,
                reduced_validation,
                strategy="collision_aware_reduced",
                label="Collision-aware reduced-magnitude candidate",
                model_name=ENGINE_NAME,
                limitations=(
                    "Uniform 0.75 geometric scale of explicit movements.",
                    "Not biomechanical collision resolution.",
                    "Rejected candidates remain listed with validation findings.",
                ),
                is_active=False,
            )
        )

        micro_config = StagingConfiguration(
            stage_count=max(base_config.stage_count, 4), mode="micro"
        )
        micro_staging = self._stager.generate(proposal, micro_config)
        micro_validation = self._validator.validate(micro_staging, self._validation_config)
        candidates.append(
            self._candidate(
                proposal,
                micro_staging,
                micro_validation,
                strategy="staging_micro",
                label="Micro staging proposal",
                model_name=ENGINE_NAME,
                limitations=("Staging density heuristic only; not clinical timing.",),
                is_active=False,
            )
        )

        macro_config = StagingConfiguration(
            stage_count=max(2, min(base_config.stage_count, 3)), mode="macro"
        )
        macro_staging = self._stager.generate(proposal, macro_config)
        macro_validation = self._validator.validate(macro_staging, self._validation_config)
        candidates.append(
            self._candidate(
                proposal,
                macro_staging,
                macro_validation,
                strategy="staging_macro",
                label="Macro staging proposal",
                model_name=ENGINE_NAME,
                limitations=("Staging density heuristic only; not clinical timing.",),
                is_active=False,
            )
        )
        return candidates

    def _rebuild_scaled(
        self,
        proposal: TreatmentPlanProposal,
        factor: float,
        *,
        tag: str,
        lateral_scale: float | None = None,
        anterior_scale: float | None = None,
    ) -> TreatmentPlanProposal:
        assert proposal.setup is not None
        overrides: dict[int | str, ToothMovement] = {}
        for state in proposal.setup.target_states:
            key = (
                state.tooth_ref
                if proposal.planning_mode == "semantic_only_experimental"
                else state.tooth_number
            )
            if key is None:
                continue
            movement = state.movement
            lx = lateral_scale if lateral_scale is not None else factor
            ay = anterior_scale if anterior_scale is not None else factor
            overrides[key] = ToothMovement(
                translation_x=movement.translation_x * lx,
                translation_y=movement.translation_y * ay,
                translation_z=movement.translation_z * factor,
                rotation=movement.rotation * factor,
                tip=movement.tip * factor,
                torque=movement.torque * factor,
                angulation=movement.angulation * factor,
                intrusion=movement.intrusion * factor,
                extrusion=movement.extrusion * factor,
                locked=movement.locked,
                excluded=movement.excluded,
            )
        rebuilt = self._planner.rebuild_proposal(
            proposal,
            overrides,
            proposal.edit_history,
            ProposalKind.ORIGINAL_GENERATED,
        )
        # Stable distinct version for alternative auditability.
        alt_hash = hashlib.sha256(
            json.dumps(
                {
                    "base": proposal.version_id,
                    "tag": tag,
                    "factor": factor,
                    "lateral": lateral_scale,
                    "anterior": anterior_scale,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return replace(
            rebuilt,
            version_id=alt_hash,
            provenance=DataProvenance.EXPERIMENTAL,
            warnings=rebuilt.warnings
            + ("Experimental assisted candidate; doctor decision required.",),
        )

    def _candidate(
        self,
        proposal: TreatmentPlanProposal,
        staging: StagingResult,
        validation: TreatmentValidationReport,
        *,
        strategy: str,
        label: str,
        model_name: str,
        limitations: tuple[str, ...],
        is_active: bool,
    ) -> IntelligenceCandidate:
        collision_count = sum(
            1
            for stage in validation.stage_results
            for item in stage.collision_results
            if item.intersects
        )
        proximity_count = sum(
            1
            for stage in validation.stage_results
            for item in stage.proximity_results
            if item.status is ValidationStatus.WARNING
        )
        contact_count = sum(
            1
            for stage in validation.stage_results
            for item in stage.contact_results
            if item.is_contact
        )
        status = validation.status.value
        findings = tuple(validation.warnings) + tuple(validation.errors)
        if validation.status is ValidationStatus.ERROR or validation.errors:
            decision = DecisionState.REJECTED_BY_VALIDATION
        else:
            decision = DecisionState.VALIDATED

        contract = ModelOutputContract(
            model_name=model_name,
            model_version=ENGINE_VERSION,
            input_provenance=proposal.provenance.value,
            confidence=None,
            uncertainty=None,
            limitations=limitations,
            deterministic_validation_status=status,
            deterministic_validation_findings=findings,
            decision_state=decision,
        )
        alternative_id = hashlib.sha256(
            f"{proposal.version_id}:{strategy}:{staging.staging_id}".encode()
        ).hexdigest()[:16]
        summary = SetupAlternativeSummary(
            alternative_id=alternative_id,
            strategy=strategy,
            label=label,
            contract=contract,
            collision_count=collision_count,
            proximity_count=proximity_count,
            contact_count=contact_count,
            stage_count=len(staging.stages),
            is_active=is_active,
        )
        return IntelligenceCandidate(
            summary=summary,
            proposal=proposal,
            staging=staging,
            validation=validation,
        )
