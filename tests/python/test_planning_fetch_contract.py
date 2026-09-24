import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.store import case_store


def test_persisted_case_lifecycle_uses_one_uuid(tmp_path, monkeypatch) -> None:
    path = tmp_path / "cases.json"
    monkeypatch.setattr(case_store, "path", path)
    case_store.clear()
    client = TestClient(app)
    created = client.post("/cases", json={"patient_reference": "persisted"})
    case_id = created.json()["id"]
    assert json.loads(path.read_text())[0]["id"] == case_id

    reloaded_store = type(case_store)(path)
    assert reloaded_store.get(case_id) is not None
    assert reloaded_store.get(case_id).id == case_id
    case_store.clear()


def test_planning_failure_is_structured_not_a_fetch_error(monkeypatch) -> None:
    client = TestClient(app)
    response = client.post("/cases", json={"patient_reference": "planning"})
    case_id = response.json()["id"]
    plan = client.post(f"/cases/{case_id}/plan")
    assert plan.status_code == 400
    assert "Both upper and lower STL files are required" in plan.json()["detail"]
    case_store.clear()
