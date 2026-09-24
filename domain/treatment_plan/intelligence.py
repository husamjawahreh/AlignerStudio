"""P6 model-assisted planning contracts — provenance, validation gate, doctor decision."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IntelligenceCapabilityStatus(str, Enum):
    """Honest availability for advanced planning capabilities."""

    COMPUTED = "computed"
    UNAVAILABLE = "unavailable"
    BOUNDARY_ONLY = "boundary_only"
    REJECTED = "rejected"


class DecisionState(str, Enum):
    """Doctor decision gate — AI never auto-accepts."""

    PROPOSED = "proposed"
    VALIDATED = "validated"
    REJECTED_BY_VALIDATION = "rejected_by_validation"
    ACCEPTED_BY_DOCTOR = "accepted_by_doctor"
    DECLINED_BY_DOCTOR = "declined_by_doctor"


@dataclass(frozen=True)
class ModelOutputContract:
    """Mandatory metadata for every model/assisted planning output (Master Plan §10)."""

    model_name: str
    model_version: str
    input_provenance: str
    confidence: float | None
    uncertainty: float | None
    limitations: tuple[str, ...]
    deterministic_validation_status: str
    deterministic_validation_findings: tuple[str, ...]
    decision_state: DecisionState

    def payload(self) -> dict[str, object]:
        return {
            "modelName": self.model_name,
            "modelVersion": self.model_version,
            "inputProvenance": self.input_provenance,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "limitations": list(self.limitations),
            "deterministicValidationStatus": self.deterministic_validation_status,
            "deterministicValidationFindings": list(self.deterministic_validation_findings),
            "decisionState": self.decision_state.value,
        }


@dataclass(frozen=True)
class ResearchAdapterEvaluation:
    """Evidence record for a research model — never implies production integration."""

    adapter_id: str
    model_name: str
    product_problem: str
    decision: str
    status: IntelligenceCapabilityStatus
    model_version: str | None
    provenance_notes: str
    benchmark_status: str
    limitations: tuple[str, ...]
    compared_to_deterministic_validation: str

    def payload(self) -> dict[str, object]:
        return {
            "adapterId": self.adapter_id,
            "modelName": self.model_name,
            "productProblem": self.product_problem,
            "decision": self.decision,
            "status": self.status.value,
            "modelVersion": self.model_version,
            "provenanceNotes": self.provenance_notes,
            "benchmarkStatus": self.benchmark_status,
            "limitations": list(self.limitations),
            "comparedToDeterministicValidation": self.compared_to_deterministic_validation,
        }


@dataclass(frozen=True)
class SetupAlternativeSummary:
    """Reviewable alternative setup — doctor selects; AI never auto-applies."""

    alternative_id: str
    strategy: str
    label: str
    contract: ModelOutputContract
    collision_count: int
    proximity_count: int
    contact_count: int
    stage_count: int
    is_active: bool

    def payload(self) -> dict[str, object]:
        return {
            "alternativeId": self.alternative_id,
            "strategy": self.strategy,
            "label": self.label,
            "contract": self.contract.payload(),
            "collisionCount": self.collision_count,
            "proximityCount": self.proximity_count,
            "contactCount": self.contact_count,
            "stageCount": self.stage_count,
            "isActive": self.is_active,
        }


@dataclass(frozen=True)
class PlanningIntelligenceReport:
    """P6 capability map + alternatives + research adapter evaluations."""

    landmark_assisted_target_setup: IntelligenceCapabilityStatus
    arch_form_aware_planning: IntelligenceCapabilityStatus
    occlusion_aware_planning: IntelligenceCapabilityStatus
    collision_aware_candidate_generation: IntelligenceCapabilityStatus
    constrained_six_dof_trajectories: IntelligenceCapabilityStatus
    staging_proposals: IntelligenceCapabilityStatus
    alternative_setups: IntelligenceCapabilityStatus
    alternatives: tuple[SetupAlternativeSummary, ...]
    research_adapters: tuple[ResearchAdapterEvaluation, ...]
    notes: tuple[str, ...]
    doctor_decision_required: bool = True

    def payload(self) -> dict[str, object]:
        return {
            "landmarkAssistedTargetSetup": self.landmark_assisted_target_setup.value,
            "archFormAwarePlanning": self.arch_form_aware_planning.value,
            "occlusionAwarePlanning": self.occlusion_aware_planning.value,
            "collisionAwareCandidateGeneration": self.collision_aware_candidate_generation.value,
            "constrainedSixDofTrajectories": self.constrained_six_dof_trajectories.value,
            "stagingProposals": self.staging_proposals.value,
            "alternativeSetups": self.alternative_setups.value,
            "alternatives": [item.payload() for item in self.alternatives],
            "researchAdapters": [item.payload() for item in self.research_adapters],
            "notes": list(self.notes),
            "doctorDecisionRequired": self.doctor_decision_required,
            "rule": "AI proposes. Deterministic geometry validates. Doctor decides.",
        }
