"""P0.1: real-case treatment presentation must include both arches (14+14)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.routers.cases import _combined_fixture_identification
from app.store import case_store
from app.treatment_sessions import review_bundle, treatment_sessions
from domain.case.models import MeshAsset
from domain.case.provenance import DataProvenance
from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
from domain.treatment_plan.setup import ToothMovement, TreatmentObjective, TreatmentObjectiveType
from domain.treatment_plan.validation import (
    StageValidationResult,
    TreatmentValidationReport,
    ValidationStatus,
)
from engines.planning.setup_engine import TreatmentPlanningEngine

ARTIFACT = Path(__file__).resolve().parents[2] / "official_real_case_stage2_verified_v1.zip"


def _fast_validate(self, staging, configuration):  # noqa: ANN001, ARG001
    stage_results = tuple(
        StageValidationResult(
            stage_index=stage.stage_index,
            stage_id=stage.stage_id,
            tooth_results=(),
            proximity_results=(),
            collision_results=(),
            contact_results=(),
            status=ValidationStatus.PASS,
            provenance=DataProvenance.GENERATED,
        )
        for stage in staging.stages
    )
    return TreatmentValidationReport(
        plan_id=getattr(staging, "plan_id", "fast-validate"),
        report_id="fast-validate",
        stage_results=stage_results,
        status=ValidationStatus.PASS,
        provenance=DataProvenance.GENERATED,
        fixture=True,
    )


def test_combined_fixture_identification_has_both_arches(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE", str(ARTIFACT))

    identification, _diagnostics = _combined_fixture_identification()
    upper = [tooth for tooth in identification.teeth if tooth.instance.arch == "upper"]
    lower = [tooth for tooth in identification.teeth if tooth.instance.arch == "lower"]
    assert len(upper) == 14
    assert len(lower) == 14
    assert all(tooth.identity is None for tooth in identification.teeth)
    assert {tooth.tooth_ref for tooth in upper} == {f"upper:instance:{i}" for i in range(14)}
    assert {tooth.tooth_ref for tooth in lower} == {f"lower:instance:{i}" for i in range(14)}


def test_semantic_setup_and_review_bundle_preserve_both_arches(monkeypatch) -> None:
    """Planning/setup + review DTO must carry both arches; skip heavy pair validation."""
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE", str(ARTIFACT))
    monkeypatch.setenv("ALIGNERSTUDIO_STAGE_COUNT", "2")
    monkeypatch.setattr(
        "engines.validation.geometric_engine.GeometricValidationEngine.validate",
        _fast_validate,
    )

    identification, diagnostics = _combined_fixture_identification()
    treatment_input = TreatmentPlanningInput.from_identification(
        identification,
        diagnostics=diagnostics,
        planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL,
    )
    refs = [tooth.tooth_ref for tooth in identification.teeth]
    objectives = (
        TreatmentObjective(
            "p0-1-two-arch",
            TreatmentObjectiveType.ALIGNMENT,
            "Presentation check only.",
            ((refs[0], ToothMovement(translation_x=0.2)),),
        ),
    )
    proposal = TreatmentPlanningEngine().generate_from_input(
        "p0-1-two-arch", treatment_input, objectives
    )
    assert proposal.setup is not None
    assert len(proposal.setup.target_states) == 28
    assert sum(1 for state in proposal.setup.target_states if state.arch == "upper") == 14
    assert sum(1 for state in proposal.setup.target_states if state.arch == "lower") == 14

    session = treatment_sessions.create_from_treatment_input(
        "p0-1-two-arch-session", treatment_input, objectives
    )
    bundle = review_bundle(session)
    teeth = bundle["stages"][0]["teeth"]
    assert len(teeth) == 28
    assert sum(1 for tooth in teeth if tooth["arch"] == "upper") == 14
    assert sum(1 for tooth in teeth if tooth["arch"] == "lower") == 14
    assert all(tooth["fdiNumber"] is None for tooth in teeth)
    assert len({tooth["instanceId"] for tooth in teeth}) == 28
    assert all(tooth["toothRef"].startswith(("upper:", "lower:")) for tooth in teeth)


def test_plan_endpoint_wires_both_arches_into_treatment_session(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE", str(ARTIFACT))
    monkeypatch.setenv("ALIGNERSTUDIO_STAGE_COUNT", "2")
    monkeypatch.setattr(
        "engines.validation.geometric_engine.GeometricValidationEngine.validate",
        _fast_validate,
    )
    case_store.clear()
    treatment_sessions.clear()
    client = TestClient(app)
    case_id = client.post("/cases", json={"patient_reference": "p0-1-api"}).json()["id"]
    case = case_store.get(case_id)
    assert case is not None
    case.meshes = [
        MeshAsset("upper", "/tmp/upper.stl", "upper.stl"),
        MeshAsset("lower", "/tmp/lower.stl", "lower.stl"),
    ]
    case_store.update(case)

    plan = client.post(f"/cases/{case_id}/plan")
    assert plan.status_code == 200, plan.text
    treatment = client.get(f"/cases/{case_id}/treatment")
    assert treatment.status_code == 200, treatment.text
    teeth = treatment.json()["stages"][0]["teeth"]
    assert len(teeth) == 28
    assert sum(1 for tooth in teeth if tooth["arch"] == "upper") == 14
    assert sum(1 for tooth in teeth if tooth["arch"] == "lower") == 14

    case_store.clear()
    treatment_sessions.clear()
