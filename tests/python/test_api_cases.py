from concurrent.futures import Future

import pytest
from app.main import app
from app.processing import _handle_worker_exit
from app.store import case_store
from app.treatment_sessions import treatment_sessions
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clear_store():
    case_store.clear()
    treatment_sessions.clear()
    yield
    case_store.clear()
    treatment_sessions.clear()


client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_engineering_demo_allows_local_vite_origins(origin: str) -> None:
    response = client.post("/cases/demo", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "x-alignerstudio-manifest" in response.headers["access-control-expose-headers"].lower()
    payload = response.json()
    assert {"case", "review_bundle"} <= payload.keys()
    assert payload["review_bundle"]["stages"]
    assert payload["review_bundle"]["iprSites"]
    assert payload["review_bundle"]["attachmentSites"]
    assert payload["review_bundle"]["sourceKind"] == "development_treatment_fixture"
    assert payload["review_bundle"]["experimental"] is True


def test_create_case() -> None:
    resp = client.post("/cases", json={"patient_reference": "P-1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["patient_reference"] == "P-1"
    assert body["status"] == "created"


def test_processing_status_starts_and_is_retrievable_for_same_case() -> None:
    case_id = client.post("/cases", json={"patient_reference": "processing"}).json()["id"]
    started = client.post(f"/cases/{case_id}/processing")
    assert started.status_code == 200
    assert started.json()["case_id"] == case_id
    assert 0 <= started.json()["overall_progress"] <= 100
    status = client.get(f"/cases/{case_id}/processing-status")
    assert status.status_code == 200
    assert status.json()["job_id"] == started.json()["job_id"]


def test_worker_exit_persists_terminal_failure() -> None:
    case_id = client.post("/cases", json={"patient_reference": "worker-exit"}).json()["id"]
    job_id = "worker-exit-job"
    case_store.set_processing(
        case_id,
        {
            "job_id": job_id,
            "case_id": case_id,
            "stage_status": "PROCESSING",
            "current_stage": "BUILDING_PLAN",
            "overall_progress": 70,
            "stage_progress": None,
            "completed_stages": ["VALIDATING_SCANS", "SEGMENTING_UPPER", "SEGMENTING_LOWER"],
            "pending_stages": ["BUILDING_PLAN", "VALIDATING_PLAN", "FINALIZING"],
            "started_at": "2026-01-01T00:00:00+00:00",
        },
    )
    future: Future[None] = Future()
    future.set_exception(RuntimeError("planner worker exited"))

    _handle_worker_exit(case_id, job_id, future)

    status = case_store.get_processing(case_id)
    assert status is not None
    assert status["stage_status"] == "FAILED"
    assert status["error_code"] == "PROCESSING_FAILED"
    assert "planner worker exited" in status["technical_diagnostic"]


def test_real_case_identity_survives_retrieval_and_downstream_requests() -> None:
    created = client.post("/cases", json={"patient_reference": "lifecycle"})
    case_id = created.json()["id"]

    retrieved = client.get(f"/cases/{case_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == case_id

    pipeline = client.post(f"/cases/{case_id}/pipeline/upper")
    assert pipeline.status_code == 404
    assert pipeline.json()["detail"] == "No uploaded mesh for arch 'upper'"

    plan = client.post(f"/cases/{case_id}/plan")
    assert plan.status_code != 404


def test_full_slice_upload_validate_plan(tmp_path) -> None:
    import trimesh

    stl_path = tmp_path / "arch.stl"
    trimesh.creation.icosphere(subdivisions=4, radius=5.0).export(stl_path)

    case_resp = client.post("/cases", json={"patient_reference": "P-2"})
    case_id = case_resp.json()["id"]

    with open(stl_path, "rb") as f:
        upload_resp = client.post(
            f"/cases/{case_id}/uploads",
            params={"arch": "upper"},
            files={"file": ("arch.stl", f, "application/octet-stream")},
        )
    assert upload_resp.status_code == 200
    assert upload_resp.json()["status"] == "mesh_uploaded"

    validate_resp = client.post(f"/cases/{case_id}/uploads/upper/validate")
    assert validate_resp.status_code == 200
    assert validate_resp.json()["is_valid"] is True

    plan_resp = client.post(f"/cases/{case_id}/plan")
    assert plan_resp.status_code == 400
    assert "missing: lower" in plan_resp.json()["detail"]

    pipeline_resp = client.post(f"/cases/{case_id}/pipeline/upper")
    assert pipeline_resp.status_code == 200
    diagnostic = pipeline_resp.json()
    assert diagnostic["state"] == "model_unavailable"
    assert diagnostic["source_kind"] == "uploaded_real_case"
    assert diagnostic["tooth_instance_count"] == 0
    assert "No fixture fallback" in diagnostic["failures"][0]


@pytest.mark.parametrize("arch", ["upper", "lower"])
def test_plan_requires_both_arches(tmp_path, arch: str) -> None:
    import trimesh

    stl_path = tmp_path / f"{arch}.stl"
    trimesh.creation.icosphere(subdivisions=4, radius=5.0).export(stl_path)
    case_id = client.post("/cases", json={}).json()["id"]
    with open(stl_path, "rb") as file:
        response = client.post(
            f"/cases/{case_id}/uploads",
            params={"arch": arch},
            files={"file": (stl_path.name, file, "application/octet-stream")},
        )
    assert response.status_code == 200
    plan = client.post(f"/cases/{case_id}/plan")
    assert plan.status_code == 400
    assert ("lower" if arch == "upper" else "upper") in plan.json()["detail"]


def test_both_arches_upload_and_remove_without_fixture_fallback(tmp_path) -> None:
    import trimesh

    stl_path = tmp_path / "arch.stl"
    trimesh.creation.icosphere(subdivisions=4, radius=5.0).export(stl_path)
    case_id = client.post("/cases", json={}).json()["id"]
    for expected_arches, arch in (({"upper"}, "upper"), ({"upper", "lower"}, "lower")):
        with open(stl_path, "rb") as file:
            response = client.post(
                f"/cases/{case_id}/uploads",
                params={"arch": arch},
                files={"file": (f"{arch}.stl", file, "application/octet-stream")},
            )
        assert response.status_code == 200
        assert {mesh["arch"] for mesh in response.json()["meshes"]} == expected_arches
    plan = client.post(f"/cases/{case_id}/plan")
    assert plan.status_code == 503
    detail = plan.json()["detail"]
    assert "fixture substitution is not used" in detail.lower() or "no fake segmentation fallback" in detail.lower()
    assert "run analysis" in detail.lower() or "segmentation" in detail.lower()
    removed = client.delete(f"/cases/{case_id}/uploads/lower")
    assert removed.status_code == 200
    assert [mesh["arch"] for mesh in removed.json()["meshes"]] == ["upper"]


def test_upload_rejects_non_stl(tmp_path) -> None:
    case_resp = client.post("/cases", json={})
    case_id = case_resp.json()["id"]
    bad_file = tmp_path / "notes.txt"
    bad_file.write_text("hello")
    with open(bad_file, "rb") as f:
        resp = client.post(
            f"/cases/{case_id}/uploads",
            params={"arch": "upper"},
            files={"file": ("notes.txt", f, "text/plain")},
        )
    assert resp.status_code == 400


def test_engineering_demo_runs_review_edit_recalculate_proposals_and_export() -> None:
    demo = client.post("/cases/demo")
    assert demo.status_code == 200
    payload = demo.json()
    case_id = payload["case"]["id"]
    bundle = payload["review_bundle"]
    assert bundle["fixture"] is True
    assert bundle["realDataAvailable"] is True
    assert [stage["index"] for stage in bundle["stages"]] == [0, 1, 2]

    treatment = client.get(f"/cases/{case_id}/treatment")
    assert treatment.status_code == 200
    assert treatment.json()["stages"][0]["stageId"] == bundle["stages"][0]["stageId"]

    edited = client.post(
        f"/cases/{case_id}/treatment/edits",
        json={"tooth_number": 11, "translation_x": 0.4},
    )
    assert edited.status_code == 200
    assert edited.json()["editHistory"]

    recalculated = client.post(f"/cases/{case_id}/treatment/recalculate")
    assert recalculated.status_code == 200
    assert recalculated.json()["proposalKind"] == "recalculated"

    proposals = client.get(f"/cases/{case_id}/treatment/proposals")
    assert proposals.status_code == 200
    assert proposals.json()["iprSites"]

    exported = client.post(f"/cases/{case_id}/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/zip")
    assert exported.content[:2] == b"PK"
    assert '"fixture":true' in exported.headers["x-alignerstudio-manifest"]
