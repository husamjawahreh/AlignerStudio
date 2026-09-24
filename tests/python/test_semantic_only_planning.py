from fastapi.testclient import TestClient

from app.main import app
from app.store import case_store
from domain.case.models import MeshAsset


def test_semantic_only_planning_does_not_crash_on_missing_fdi(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv(
        "ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE",
        "/home/hjawahreh/Desktop/Projects/AlignerStudio/official_real_case_stage2_verified_v1.zip",
    )
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
    # The endpoint must return a structured planning response/error, never an uncaught 500.
    response = client.post(f"/cases/{case_id}/plan")
    assert response.status_code in {400, 409, 503}
    assert response.status_code != 500
    case_store.clear()
