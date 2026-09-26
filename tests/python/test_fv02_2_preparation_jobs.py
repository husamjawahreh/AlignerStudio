"""FV-02.2 preparation jobs, cache, lineage, and the technical acceptance gate."""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

import pytest
import trimesh
from app.store import InMemoryCaseStore
from fastapi.testclient import TestClient

from domain.case.preparation import preparation_cache_key
from engines.geometry.intake_inspection import inspect_source_file
from engines.geometry.preparation_jobs import (
    PreparationJobConflict,
    cancel_preparation_job,
    measure_preparation_reliability,
    reset_preparation_jobs,
    run_preparation_job,
    set_preparation_checkpoint_hook,
    submit_preparation_job,
    wait_preparation_job,
)
from engines.geometry.scan_preparation import (
    accept_preparation,
    apply_operation,
    evaluate_prepared_input,
    retire_unreferenced_outputs,
)


@pytest.fixture(autouse=True)
def _clear_jobs() -> None:
    reset_preparation_jobs()
    yield
    set_preparation_checkpoint_hook(None)
    reset_preparation_jobs()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _box(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trimesh.creation.box().export(path)


def _artifact(path: Path, arch: str = "upper") -> dict:
    return inspect_source_file(
        path, case_id="case-1", explicit_arch=arch, original_filename=path.name
    )


def _orient() -> dict:
    return {"method": "user_transform", "rotation_deg": [0, 0, 90], "translation": [0, 0, 0]}


def test_job_lifecycle_does_not_block_and_publishes_a_complete_mesh(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    before = path.read_bytes()
    artifact = _artifact(path)
    entered = threading.Event()
    release = threading.Event()

    def hook(stage: str) -> None:
        if stage == "operate":
            entered.set()
            assert release.wait(5)

    set_preparation_checkpoint_hook(hook)
    queued = submit_preparation_job(
        artifact,
        case_id="case-1",
        arch="upper",
        operation="orient",
        parameters=_orient(),
        mode="apply",
    )
    assert queued["state"] == "queued"
    assert queued["job_id"]
    assert queued["case_id"] == "case-1"
    assert queued["source_artifact_hash"] == _sha(path)
    assert queued["operation"] == "orient"
    assert queued["progress"] == 0.0
    assert entered.wait(5)
    assert artifact.get("preparation", {}).get("active") is None
    release.set()
    finished = wait_preparation_job(queued["job_id"])
    assert finished["state"] == "completed"
    assert finished["started_at"] and finished["ended_at"]
    assert finished["duration_ms"] >= 0
    assert finished["progress"] == 1.0
    assert finished["output_artifact_hash"]
    assert finished["error"] is None
    assert finished["clinical_axes"] is False
    active = artifact["preparation"]["active"]
    assert active["output_sha256"] == finished["output_artifact_hash"]
    assert Path(active["output_path"]).is_file()
    assert not list(tmp_path.glob("*.partial"))
    assert path.read_bytes() == before


def test_cancel_before_commit_publishes_nothing_and_keeps_provenance(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _artifact(path)
    entered = threading.Event()
    release = threading.Event()

    def hook(stage: str) -> None:
        if stage == "commit":
            entered.set()
            assert release.wait(5)

    set_preparation_checkpoint_hook(hook)
    queued = submit_preparation_job(
        artifact,
        case_id="case-1",
        arch="upper",
        operation="trim",
        parameters={
            "region": "axis_aligned_box",
            "minimum": [-0.2, -1, -1],
            "maximum": [1, 1, 1],
        },
        mode="apply",
    )
    assert entered.wait(5)
    cancelled = cancel_preparation_job(queued["job_id"])
    assert cancelled is not None
    release.set()
    finished = wait_preparation_job(queued["job_id"])
    assert finished["state"] == "cancelled"
    assert finished["error"]["code"] == "CANCELLED"
    assert finished["output_artifact_hash"] is None
    assert artifact["preparation"].get("active") is None
    assert list(tmp_path.glob("*-prepared-v*.stl")) == []
    assert list(tmp_path.glob("*.partial")) == []
    events = artifact["preparation"]["provenance_events"]
    assert events[-1]["state"] == "cancelled"
    assert events[-1]["published"] is False
    assert events[-1]["source_sha256"] == _sha(path)


def test_stale_job_does_not_overwrite_a_newer_prepared_mesh(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _artifact(path)
    first = apply_operation(artifact, "orient", _orient())
    current = first["active"]["output_sha256"]
    current_path = Path(first["active"]["output_path"])
    before = current_path.read_bytes()
    queued = submit_preparation_job(
        artifact,
        case_id="case-1",
        arch="upper",
        operation="cleanup",
        parameters={
            "merge_duplicate_vertices": True,
            "remove_degenerate_faces": True,
            "remove_duplicate_faces": False,
            "remove_invalid_components": False,
        },
        mode="apply",
        schedule=False,
    )
    artifact["preparation"]["commit_generation"] = int(first["commit_generation"]) + 3
    finished = run_preparation_job(queued["job_id"])
    assert finished is not None
    assert finished["state"] == "failed"
    assert finished["error"]["code"] == "STALE_JOB"
    assert artifact["preparation"]["active"]["output_sha256"] == current
    assert current_path.read_bytes() == before
    assert artifact["preparation"]["provenance_events"][-1]["published"] is False


def test_cache_hit_records_reuse_and_does_not_cross_source_hash(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _artifact(path)
    first = submit_preparation_job(
        artifact,
        case_id="case-1",
        arch="upper",
        operation="orient",
        parameters=_orient(),
        mode="apply",
        schedule=False,
    )
    computed = run_preparation_job(first["job_id"])
    assert computed is not None
    assert computed["cache_hit"] is False
    assert computed["state"] == "completed"
    truth = artifact["preparation"]["operations"][0]["truth_state"]
    other = tmp_path / "other" / "scan.stl"
    _box(other)
    reused_artifact = _artifact(other)
    second = submit_preparation_job(
        reused_artifact,
        case_id="case-2",
        arch="upper",
        operation="orient",
        parameters=_orient(),
        mode="apply",
        schedule=False,
    )
    hit = run_preparation_job(second["job_id"])
    assert hit is not None
    assert hit["cache_hit"] is True
    assert hit["reused"] is True
    assert hit["output_artifact_hash"] == computed["output_artifact_hash"]
    assert reused_artifact["preparation"]["operations"][0]["truth_state"] == truth
    assert reused_artifact["preparation"]["operations"][0]["clinical_axes"] is False
    assert reused_artifact["preparation"]["clinical_axes"] is False
    assert reused_artifact["preparation"]["fdi_assigned"] is False
    assert reused_artifact["preparation"]["versions"][-1]["reused"] is True
    changed = tmp_path / "changed.stl"
    changed.write_bytes(path.read_bytes() + b" ")
    changed_artifact = _artifact(changed)
    third = submit_preparation_job(
        changed_artifact,
        case_id="case-3",
        arch="upper",
        operation="orient",
        parameters=_orient(),
        mode="apply",
        schedule=False,
    )
    miss = run_preparation_job(third["job_id"])
    assert miss is not None
    assert miss["cache_hit"] is False
    assert miss["source_artifact_hash"] != computed["source_artifact_hash"]
    prefix_key = preparation_cache_key(
        source_sha256=_sha(path),
        operation="trim",
        parameters={"region": "plane", "normal": [0, 0, 1], "offset": 0},
        algorithm="centroid_region_crop",
        algorithm_version="5.1.0",
        replay_prefix=[{"operation": "orient", "parameters": _orient()}],
    )
    bare_key = preparation_cache_key(
        source_sha256=_sha(path),
        operation="trim",
        parameters={"region": "plane", "normal": [0, 0, 1], "offset": 0},
        algorithm="centroid_region_crop",
        algorithm_version="5.1.0",
        replay_prefix=[],
    )
    assert prefix_key != bare_key


def test_lineage_and_cleanup_keep_referenced_history(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    before = path.read_bytes()
    artifact = _artifact(path)
    first = apply_operation(artifact, "orient", _orient())
    first_path = Path(first["active"]["output_path"])
    second = apply_operation(
        artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 0, 0], "translation": [1, 0, 0]},
    )
    second_path = Path(second["active"]["output_path"])
    lineage = second["lineage"]
    assert lineage[0]["lifecycle"] == "superseded"
    assert lineage[0]["cleanup"] == "cleanup_deferred"
    assert lineage[0]["cleanup_reason"] == "referenced_by_preparation_history"
    assert lineage[-1]["lifecycle"] == "active"
    assert lineage[-1]["source_sha256"] == _sha(path)
    assert lineage[-1]["output_sha256"] == second["active"]["output_sha256"]
    assert lineage[-1]["replaces_source"] is False
    assert lineage[-1]["operations"][0]["algorithm"]
    assert lineage[-1]["operations"][1]["algorithm_version"]
    orphan = tmp_path / "scan-prepared-v9.stl"
    orphan.write_bytes(b"not-a-mesh")
    partial = tmp_path / "scan-prepared-v8.stl.partial"
    partial.write_bytes(b"partial")
    report = retire_unreferenced_outputs(artifact)
    assert not orphan.exists()
    assert not partial.exists()
    assert first_path.is_file()
    assert second_path.is_file()
    assert report["used_filesystem_timestamps"] is False
    assert any(item["output_path"] == str(first_path) for item in report["cleanup_deferred"])
    assert path.read_bytes() == before


def test_acceptance_gate_rejects_failed_cancelled_and_inconsistent_inputs(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _artifact(path)
    apply_operation(artifact, "orient", _orient())
    gate = evaluate_prepared_input(artifact)
    assert gate["passed"] is True
    assert gate["clinically_ready"] is False
    assert gate["clinical_axes"] is False
    accepted = accept_preparation(artifact)
    assert accepted["technical_gate_passed"] is True
    assert accepted["technical_gate"]["clinically_ready"] is False
    assert accepted["future_segmentation_input"]["clinically_ready"] is False
    assert accepted["future_segmentation_input"]["uses_derived_hash_as_source"] is False
    assert accepted["readiness"] in {"READY_FOR_SEGMENTATION", "READY_WITH_WARNINGS"}

    failed = _artifact(path)
    apply_operation(failed, "orient", _orient())
    failed["preparation"]["active"]["job_id"] = "job-failed"
    failed["preparation"]["jobs"] = [
        {
            "job_id": "job-failed",
            "state": "failed",
            "published": True,
            "output_artifact_hash": failed["preparation"]["active"]["output_sha256"],
        }
    ]
    refused = evaluate_prepared_input(failed)
    assert refused["passed"] is False
    assert "failed_or_cancelled_job_referenced" in refused["reasons"]
    with pytest.raises(Exception, match="technically acceptable"):
        accept_preparation(failed)

    cancelled = _artifact(path)
    apply_operation(cancelled, "orient", _orient())
    cancelled["preparation"]["active"]["job_id"] = "job-cancelled"
    cancelled["preparation"]["jobs"] = [{"job_id": "job-cancelled", "state": "cancelled"}]
    cancelled_gate = evaluate_prepared_input(cancelled)
    assert "active_job_not_completed" in cancelled_gate["reasons"]

    inconsistent = _artifact(path)
    apply_operation(inconsistent, "orient", _orient())
    inconsistent["preparation"]["quality_comparison"]["prepared"]["face_count"] = 1
    mismatch = evaluate_prepared_input(inconsistent)
    assert mismatch["passed"] is False
    assert "face_count_inconsistent" in mismatch["reasons"]

    missing = _artifact(path)
    apply_operation(missing, "orient", _orient())
    path.write_bytes(b"changed")
    changed = evaluate_prepared_input(missing)
    assert "source_hash_mismatch" in changed["reasons"]


def test_duplicate_job_is_rejected_and_api_returns_before_the_mesh_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import app

    store = InMemoryCaseStore(tmp_path / "cases.json")
    monkeypatch.setattr("app.routers.cases.case_store", store)
    monkeypatch.setattr("app.preparation_jobs.case_store", store)
    monkeypatch.setattr("app.routers.cases.UPLOAD_DIR", tmp_path)
    client = TestClient(app)
    created = client.post("/cases", json={"patient_reference": "local-ref"}).json()
    stl = tmp_path / "scan.stl"
    _box(stl)
    uploaded = client.post(
        f"/cases/{created['id']}/uploads",
        params={"arch": "upper"},
        files={"file": ("scan.stl", stl.read_bytes(), "model/stl")},
    )
    assert uploaded.status_code == 200
    stored = Path(uploaded.json()["meshes"][0]["file_path"])
    before = stored.read_bytes()
    entered = threading.Event()
    release = threading.Event()

    def hook(stage: str) -> None:
        if stage == "operate":
            entered.set()
            assert release.wait(5)

    set_preparation_checkpoint_hook(hook)
    clock = time.perf_counter()
    response = client.post(
        f"/cases/{created['id']}/uploads/upper/preparation/jobs",
        json={"operation": "orient", "parameters": _orient(), "mode": "apply"},
    )
    elapsed = time.perf_counter() - clock
    assert elapsed < 1.0
    assert response.status_code == 200
    body = response.json()
    assert body["state"] in {"queued", "running"}
    assert entered.wait(5)
    duplicate = client.post(
        f"/cases/{created['id']}/uploads/upper/preparation/jobs",
        json={"operation": "orient", "parameters": _orient(), "mode": "apply"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["job_id"] == body["job_id"]
    conflict = client.post(
        f"/cases/{created['id']}/uploads/upper/preparation/jobs",
        json={
            "operation": "cleanup",
            "parameters": {"merge_duplicate_vertices": True},
            "mode": "apply",
        },
    )
    assert conflict.status_code == 409
    release.set()
    deadline = time.perf_counter() + 10
    final = body
    while time.perf_counter() < deadline:
        current = client.get(
            f"/cases/{created['id']}/uploads/upper/preparation/jobs/{body['job_id']}"
        )
        assert current.status_code == 200
        final = current.json()
        if final["state"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.05)
    assert final["state"] == "completed"
    reopened = client.get(f"/cases/{created['id']}")
    preparation = reopened.json()["intake_artifacts"][0]["preparation"]
    assert preparation["readiness"] == "PREPARED"
    assert preparation["clinical_axes"] is False
    assert preparation["fdi_assigned"] is False
    assert stored.read_bytes() == before


def test_direct_conflict_names_the_active_arch(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _artifact(path)
    entered = threading.Event()
    release = threading.Event()

    def hook(stage: str) -> None:
        if stage == "load":
            entered.set()
            assert release.wait(5)

    set_preparation_checkpoint_hook(hook)
    submit_preparation_job(
        artifact,
        case_id="case-1",
        arch="upper",
        operation="orient",
        parameters=_orient(),
        mode="preview",
    )
    assert entered.wait(5)
    with pytest.raises(PreparationJobConflict, match="already active"):
        submit_preparation_job(
            artifact,
            case_id="case-1",
            arch="upper",
            operation="trim",
            parameters={"region": "plane", "normal": [1, 0, 0], "offset": -10},
            mode="preview",
        )
    release.set()


def test_real_scan_reliability_measurement() -> None:
    source = Path("data/benchmark/real-case/upper.stl")
    if not source.is_file():
        pytest.skip("Real FV-02 STL is not in this checkout.")
    if source.stat().st_size != 8_557_034:
        pytest.skip("Real FV-02 STL size does not match the measured file.")
    work = Path(".research/tmp/fv02_2_reliability")
    if work.exists():
        for child in work.iterdir():
            if child.is_file():
                child.unlink()
    report = measure_preparation_reliability(source, work)
    assert report["file_size"] == 8_557_034
    assert report["vertex_count"] == 513_417
    assert report["face_count"] == 171_139
    assert report["source_sha256"] == (
        "60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48"
    )
    assert report["source_unchanged"] is True
    assert report["cache_hit"] is True
    assert report["clinical_axes"] is False
    assert report["fdi_assigned"] is False
    assert report["clinically_ready"] is False
    assert report["commit_state"] == "completed"
    assert report["cache_hit_ms"] < report["commit_ms"]
    assert report["manifold3d_used"] is False
    assert report["meshlib_used"] is False
    assert report["peak_rss_mb"] > 0
