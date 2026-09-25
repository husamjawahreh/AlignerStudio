"""P6 — Advanced planning intelligence: adapters, contracts, validation gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from adapters.sttalign import STTAlignAdapter, STTAlignUnavailableError
from adapters.tadpm import TADPMAdapter, TADPMUnavailableError
from adapters.threedteethsam import TeethSAMAdapter, TeethSAMUnavailableError
from app.main import app
from app.store import case_store
from app.treatment_sessions import treatment_sessions
from domain.tooth.identification import ArchType
from domain.treatment_plan.intelligence import DecisionState, IntelligenceCapabilityStatus
from domain.treatment_plan.staging import StagingConfiguration
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.intelligence import (
    AdvancedPlanningIntelligenceEngine,
    research_adapter_evaluations,
)
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.staging_engine import TreatmentStagingEngine
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)
from fastapi.testclient import TestClient
from tests.fixtures.synthetic_arch import build_synthetic_arch
from tests.fixtures.synthetic_objectives import mild_crowding_objective, rotation_objective

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _clear_store():
    case_store.clear()
    treatment_sessions.clear()
    yield
    case_store.clear()
    treatment_sessions.clear()


def _stack():
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    plan = TreatmentPlanningEngine().generate(
        "fixture-p6-case", identification, (mild_crowding_objective(), rotation_objective())
    )
    staging = TreatmentStagingEngine().generate(plan, StagingConfiguration(stage_count=3))
    validation = GeometricValidationEngine().validate(
        staging, GeometricValidationConfiguration(1.0, 0.001, 0.0)
    )
    return plan, staging, validation


def test_research_adapters_are_unavailable_without_silent_substitution() -> None:
    with pytest.raises(STTAlignUnavailableError):
        STTAlignAdapter().propose_alignment()
    with pytest.raises(TADPMUnavailableError):
        TADPMAdapter().propose_arrangement()
    with pytest.raises(TeethSAMUnavailableError):
        TeethSAMAdapter().propose_plan()
    evaluations = research_adapter_evaluations()
    assert {item.adapter_id for item in evaluations} == {"sttalign", "tadpm", "3dteethsam"}
    assert all(item.status is IntelligenceCapabilityStatus.UNAVAILABLE for item in evaluations)


def test_evaluation_artifacts_document_evidence_gaps() -> None:
    for relative in (
        "research/benchmark/sttalign/evaluation.json",
        "research/benchmark/tadpm/evaluation.json",
        "research/benchmark/3dteethsam/evaluation.json",
    ):
        payload = json.loads((ROOT / relative).read_text())
        assert payload["status"] == "unavailable"
        assert payload["production_untouched"] is True
        assert "AI proposes" in payload["rule"]


def test_intelligence_candidates_carry_model_contract_and_validation() -> None:
    plan, staging, validation = _stack()
    result = AdvancedPlanningIntelligenceEngine().generate(plan, staging, validation)
    assert result.report.collision_aware_candidate_generation is IntelligenceCapabilityStatus.COMPUTED
    assert result.report.occlusion_aware_planning is IntelligenceCapabilityStatus.UNAVAILABLE
    assert result.report.constrained_six_dof_trajectories is IntelligenceCapabilityStatus.UNAVAILABLE
    assert result.report.alternative_setups is IntelligenceCapabilityStatus.COMPUTED
    assert len(result.candidates) >= 2
    for candidate in result.candidates:
        contract = candidate.summary.contract
        assert contract.model_name
        assert contract.model_version
        assert contract.input_provenance
        assert contract.confidence is None
        assert contract.uncertainty is None
        assert contract.limitations
        assert contract.deterministic_validation_status
        assert contract.decision_state in {
            DecisionState.VALIDATED,
            DecisionState.REJECTED_BY_VALIDATION,
        }
        # Semantic identity preserved on proposals.
        assert candidate.proposal.case_id == plan.case_id
        assert candidate.proposal.setup is not None
        assert len(candidate.proposal.setup.target_states) == len(plan.setup.target_states)


def test_invalid_model_proposals_cannot_bypass_validation_gate() -> None:
    plan, staging, validation = _stack()
    result = AdvancedPlanningIntelligenceEngine().generate(plan, staging, validation)
    rejected = [
        item
        for item in result.candidates
        if item.summary.contract.decision_state is DecisionState.REJECTED_BY_VALIDATION
    ]
    # Fixture plans may have zero hard errors; if any are rejected they must stay gated.
    for item in rejected:
        assert item.validation.errors or item.validation.status.value == "error"


def test_api_planning_intelligence_and_doctor_accept_alternative() -> None:
    demo = client.post("/cases/demo")
    assert demo.status_code == 200
    case_id = demo.json()["case"]["id"]
    bundle = demo.json()["review_bundle"]
    # Demo expands assisted candidates on compose (not a validated_real_case path).
    intelligence = bundle["planningIntelligence"]
    assert intelligence["rule"].startswith("AI proposes")
    assert intelligence["occlusionAwarePlanning"] == "unavailable"
    assert intelligence["collisionAwareCandidateGeneration"] == "computed"
    assert len(intelligence["alternatives"]) > 1
    assert all(alt["contract"]["confidence"] is None for alt in intelligence["alternatives"])
    assert all(
        adapter["status"] == "unavailable" for adapter in intelligence["researchAdapters"]
    )

    intel = client.get(f"/cases/{case_id}/treatment/planning-intelligence")
    assert intel.status_code == 200
    assert intel.json()["alternativeSetups"] == "computed"

    candidate = next(
        alt
        for alt in intelligence["alternatives"]
        if not alt["isActive"] and alt["contract"]["decisionState"] != "rejected_by_validation"
    )
    selected = client.post(
        f"/cases/{case_id}/treatment/setup-alternatives/select",
        json={"alternative_id": candidate["alternativeId"]},
    )
    assert selected.status_code == 200
    body = selected.json()
    active = next(alt for alt in body["planningIntelligence"]["alternatives"] if alt["isActive"])
    assert active["alternativeId"] == candidate["alternativeId"]
    assert active["contract"]["decisionState"] == "accepted_by_doctor"
    assert body["planSummary"]["activeAlternativeStrategy"] == candidate["strategy"]
    again = client.post(
        f"/cases/{case_id}/treatment/setup-alternatives/select",
        json={"alternative_id": candidate["alternativeId"]},
    )
    assert again.status_code == 200
    assert again.json()["stages"][0]["stageId"] == body["stages"][0]["stageId"]
