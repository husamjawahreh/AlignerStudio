from domain.case.provenance import DataProvenance
from domain.case.models import MeshAsset
from domain.treatment_plan.validation import (
    StageValidationResult,
    TreatmentValidationReport,
    ValidationStatus,
)
from fastapi.testclient import TestClient

from app.main import app
from app.store import case_store
from app.treatment_sessions import treatment_sessions


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


def test_semantic_only_planning_does_not_crash_on_missing_fdi(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
    monkeypatch.setenv(
        "ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE",
        "/home/hjawahreh/Desktop/Projects/AlignerStudio/official_real_case_stage2_verified_v1.zip",
    )
    monkeypatch.setenv("ALIGNERSTUDIO_STAGE_COUNT", "2")
    monkeypatch.setattr(
        "engines.validation.geometric_engine.GeometricValidationEngine.validate",
        _fast_validate,
    )
    case_store.clear()
    treatment_sessions.clear()
    client = TestClient(app)
    created = client.post("/cases", json={"patient_reference": "semantic-plan"})
    case_id = created.json()["id"]
    case = case_store.get(case_id)
    assert case is not None
    case.meshes = [
        MeshAsset("upper", "/tmp/upper.stl", "upper.stl"),
        MeshAsset("lower", "/tmp/lower.stl", "lower.stl"),
    ]
    case_store.update(case)
    # Semantic-only planning must succeed without inventing FDI and never return 500.
    response = client.post(f"/cases/{case_id}/plan")
    assert response.status_code == 200, response.text
    assert response.status_code != 500
    treatment = client.get(f"/cases/{case_id}/treatment")
    assert treatment.status_code == 200
    teeth = treatment.json()["stages"][0]["teeth"]
    assert len(teeth) == 28
    assert all(tooth["fdiNumber"] is None for tooth in teeth)
    case_store.clear()
    treatment_sessions.clear()
