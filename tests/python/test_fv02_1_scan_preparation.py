"""FV-02.1 preparation: derived orientation, trim, cleanup, and provenance."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
import trimesh
from app.store import InMemoryCaseStore
from fastapi.testclient import TestClient

from domain.case.intake import case_arch_summary, privacy_log_view
from engines.geometry.intake_inspection import inspect_source_file
from engines.geometry.scan_preparation import (
    PreparationError,
    accept_preparation,
    apply_operation,
    preview_operation,
    reset_preparation,
    undo_preparation,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _box(path: Path) -> trimesh.Trimesh:
    mesh = trimesh.creation.box()
    mesh.export(path)
    return mesh


def _artifact(path: Path, arch: str | None) -> dict:
    return inspect_source_file(
        path, case_id="case-1", explicit_arch=arch, original_filename=path.name
    )


def test_user_orientation_persists_and_pca_is_not_clinical(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    before = path.read_bytes()
    artifact = _artifact(path, "upper")
    preview = preview_operation(
        artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 0, 90], "translation": [5, 0, 0]},
    )
    assert preview["persisted"] is False
    assert preview["clinical_axes"] is False
    assert preview["truth_state"] == "USER_PROVIDED"
    assert "preparation" not in artifact
    session = apply_operation(
        artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 0, 90], "translation": [5, 0, 0]},
    )
    assert path.read_bytes() == before
    assert session["source_sha256"] == _sha(path)
    assert session["active"]["output_sha256"] != session["source_sha256"]
    assert session["active"]["replaces_source"] is False
    assert session["operations"][0]["truth_state"] == "USER_PROVIDED"
    assert session["operations"][0]["clinical_axes"] is False
    assert session["clinical_axes"] is False
    assert session["readiness"] == "PREPARED"
    pca = apply_operation(artifact, "orient", {"method": "vertex_pca"})
    assert pca["operations"][1]["truth_state"] == "COMPUTED_GEOMETRIC_ORIENTATION"
    assert pca["operations"][1]["clinical_axes"] is False
    assert pca["clinical_axes"] is False
    assert pca["fdi_assigned"] is False
    assert "CLINICAL_ORIENTATION" not in {item["truth_state"] for item in pca["operations"]}
    again = preview_operation(
        {
            "sha256": _sha(path),
            "source_path": str(path),
            "format": "stl_binary",
            "readiness": "READY",
        },
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 0, 90], "translation": [5, 0, 0]},
    )
    first = next(item for item in session["versions"] if item["event"] == "apply")
    assert again["output_sha256"] == first["output_sha256"]


def test_trim_is_reversible_and_preview_does_not_write(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    before = path.read_bytes()
    artifact = _artifact(path, "lower")
    with pytest.raises(PreparationError, match="keeps no faces"):
        preview_operation(
            artifact,
            "trim",
            {"region": "axis_aligned_box", "minimum": [10, 10, 10], "maximum": [11, 11, 11]},
        )
    assert list(tmp_path.glob("*-prepared-*.stl")) == []
    assert path.read_bytes() == before
    session = apply_operation(
        artifact,
        "trim",
        {"region": "axis_aligned_box", "minimum": [-0.1, -1, -1], "maximum": [1, 1, 1]},
    )
    prepared_faces = session["quality_comparison"]["prepared"]["face_count"]
    source_faces = session["quality_comparison"]["source"]["face_count"]
    assert prepared_faces < source_faces
    assert session["quality_comparison"]["prepared"]["self_intersection"] == "not_run"
    assert session["active"]["geometry_class"] == "DERIVED_GEOMETRY"
    assert session["active"]["observed_anatomy"] is False
    output = session["active"]["output_sha256"]
    undone = undo_preparation(artifact)
    assert undone["readiness"] == "NOT_PREPARED"
    assert undone["active"] is None
    assert undone["source_sha256"] == _sha(path)
    assert path.read_bytes() == before
    restored = apply_operation(
        artifact,
        "trim",
        {"region": "axis_aligned_box", "minimum": [-0.1, -1, -1], "maximum": [1, 1, 1]},
    )
    assert restored["active"]["output_sha256"] == output


def test_cleanup_does_not_fill_holes_and_components_stay_explicit(tmp_path: Path) -> None:
    vertices = np.array(
        [
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1],
            [5, 0, 0],
            [5, 1e-16, 0],
            [5, 0, 1e-16],
        ],
        dtype=np.float64,
    )
    faces = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3], [4, 5, 6], [0, 1, 2]])
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    path = tmp_path / "parts.obj"
    mesh.export(path)
    before = path.read_bytes()
    artifact = _artifact(path, None)
    assert artifact["arch"]["arch"] == "ARCH_UNKNOWN"
    with pytest.raises(PreparationError, match="Hole filling"):
        apply_operation(artifact, "cleanup", {"fill_holes": True, "remove_degenerate_faces": True})
    assert path.read_bytes() == before
    listed = preview_operation(artifact, "components", {"action": "list"})
    assert len(listed["components"]) >= 2
    assert all(item["clinically_irrelevant"] is False for item in listed["components"])
    session = apply_operation(
        artifact,
        "cleanup",
        {
            "merge_duplicate_vertices": True,
            "remove_degenerate_faces": True,
            "remove_duplicate_faces": True,
            "remove_invalid_components": True,
        },
    )
    assert path.read_bytes() == before
    prepared = session["quality_comparison"]["prepared"]
    assert prepared["degenerate_faces"] == 0
    assert prepared["duplicate_face_groups"] == 0
    assert session["versions"][-1]["parameters"]["watertight_conversion"] is False
    assert session["versions"][-1]["parameters"]["hole_fill"] is False
    assert prepared["face_count"] == 4
    left = trimesh.creation.box()
    right = trimesh.creation.box()
    right.apply_translation([10, 0, 0])
    pair = tmp_path / "pair.stl"
    trimesh.util.concatenate([left, right]).export(pair)
    pair_before = pair.read_bytes()
    pair_artifact = _artifact(pair, "upper")
    listed_pair = preview_operation(pair_artifact, "components", {"action": "list"})
    assert len(listed_pair["components"]) == 2
    removed = apply_operation(
        pair_artifact,
        "components",
        {"action": "remove", "component_ids": [1], "user_marked_irrelevant": False},
    )
    assert pair.read_bytes() == pair_before
    prepared_faces = removed["quality_comparison"]["prepared"]["face_count"]
    source_faces = removed["quality_comparison"]["source"]["face_count"]
    assert prepared_faces < source_faces
    assert removed["versions"][-1]["parameters"]["user_marked_irrelevant"] is False
    assert removed["versions"][-1]["parameters"]["clinical_judgement"] is False
    assert removed["fdi_assigned"] is False


def test_quality_recheck_and_open_surface_can_be_accepted(tmp_path: Path) -> None:
    mesh = trimesh.creation.box()
    mesh.faces = mesh.faces[:-1]
    path = tmp_path / "open.stl"
    mesh.export(path)
    before = path.read_bytes()
    artifact = _artifact(path, "upper")
    session = apply_operation(
        artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 0, 0], "translation": [1, 0, 0]},
    )
    assert "boundary_edges" in session["quality_comparison"]["prepared"]
    assert session["readiness"] == "PREPARED"
    accepted = accept_preparation(artifact)
    assert accepted["readiness"] == "READY_WITH_WARNINGS"
    assert accepted["clinically_segmented"] is False
    assert accepted["fdi_assigned"] is False
    assert accepted["occlusion_established"] is False
    assert accepted["clinical_axes"] is False
    assert accepted["future_segmentation_input"]["uses_derived_hash_as_source"] is False
    assert accepted["future_segmentation_input"]["uses_prepared_mesh"] is True
    assert accepted["future_segmentation_input"]["source_sha256"] == _sha(path)
    reset = reset_preparation(artifact)
    assert reset["readiness"] == "NOT_PREPARED"
    assert reset["active"] is None
    assert reset["source_sha256"] == _sha(path)
    assert path.read_bytes() == before


def test_upper_lower_and_dual_histories_do_not_imply_occlusion(tmp_path: Path) -> None:
    upper = tmp_path / "upper.stl"
    lower = tmp_path / "lower.stl"
    _box(upper)
    shifted = trimesh.creation.box()
    shifted.apply_translation([3, 0, 0])
    shifted.export(lower)
    upper_artifact = _artifact(upper, "upper")
    lower_artifact = _artifact(lower, "lower")
    apply_operation(
        upper_artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [90, 0, 0], "translation": [0, 0, 0]},
    )
    apply_operation(
        lower_artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 90, 0], "translation": [0, 0, 0]},
    )
    summary = case_arch_summary([upper_artifact, lower_artifact])
    assert summary["upper_present"] is True
    assert summary["lower_present"] is True
    assert summary["occlusion_established"] is False
    assert summary["bite_registration_established"] is False
    assert upper_artifact["preparation"]["occlusion_established"] is False
    assert lower_artifact["preparation"]["occlusion_established"] is False
    assert upper_artifact["preparation"]["source_sha256"] != (
        lower_artifact["preparation"]["source_sha256"]
    )
    assert upper_artifact["sha256"] == _sha(upper)
    assert lower_artifact["sha256"] == _sha(lower)
    only_lower = _artifact(lower, "lower")
    accept_preparation(only_lower)
    assert only_lower["preparation"]["readiness"] in {
        "READY_FOR_SEGMENTATION",
        "READY_WITH_WARNINGS",
    }
    assert only_lower["preparation"]["occlusion_established"] is False
    unknown = _artifact(upper, None)
    assert unknown["arch"]["arch"] == "ARCH_UNKNOWN"
    assert unknown["fdi_assigned"] is False


def test_privacy_and_reopen_keep_the_source_hash(tmp_path: Path) -> None:
    from domain.case.models import Case, MeshAsset

    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _artifact(path, "upper")
    artifact["patient_reference"] = "Jane Doe"
    apply_operation(
        artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 45, 0], "translation": [0, 1, 0]},
    )
    artifact["preparation"]["active"]["output_path"] = str(tmp_path / "Jane_Doe-prepared.stl")
    logged = privacy_log_view(artifact)
    assert "Jane" not in str(logged)
    assert logged["sha256"] == artifact["sha256"]
    assert logged["preparation"]["source_sha256"] == artifact["sha256"]
    case = Case(id="c")
    case.add_mesh(MeshAsset(arch="upper", file_path=str(path), original_filename="scan.stl"))
    case.intake_artifacts = [artifact]
    InMemoryCaseStore(tmp_path / "cases.json").add(case)
    loaded = InMemoryCaseStore(tmp_path / "cases.json").get("c")
    assert loaded is not None
    saved = loaded.intake_artifacts[0]
    assert saved["sha256"] == _sha(path)
    assert saved["preparation"]["active"]["source_sha256"] == saved["sha256"]
    assert saved["preparation"]["active"]["output_sha256"] != saved["sha256"]
    assert saved["preparation"]["fdi_assigned"] is False
    assert path.read_bytes() == path.read_bytes()


def test_preparation_api_reopens_without_changing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import app

    store = InMemoryCaseStore(tmp_path / "cases.json")
    monkeypatch.setattr("app.routers.cases.case_store", store)
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
    preview = client.post(
        f"/cases/{created['id']}/uploads/upper/preparation/preview",
        json={
            "operation": "orient",
            "parameters": {
                "method": "user_transform",
                "rotation_deg": [0, 0, 90],
                "translation": [0, 0, 0],
            },
        },
    )
    assert preview.status_code == 200
    assert preview.json()["persisted"] is False
    assert stored.read_bytes() == before
    applied = client.post(
        f"/cases/{created['id']}/uploads/upper/preparation/apply",
        json={
            "operation": "cleanup",
            "parameters": {
                "merge_duplicate_vertices": True,
                "remove_degenerate_faces": True,
                "remove_duplicate_faces": True,
                "remove_invalid_components": False,
            },
        },
    )
    assert applied.status_code == 200
    body = applied.json()
    preparation = body["intake_artifacts"][0]["preparation"]
    assert preparation["readiness"] in {"PREPARED", "READY_WITH_WARNINGS", "READY_FOR_SEGMENTATION"}
    assert preparation["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert stored.read_bytes() == before
    assert body["intake_summary"]["occlusion_established"] is False
    accepted = client.post(f"/cases/{created['id']}/uploads/upper/preparation/accept")
    assert accepted.status_code == 200
    ready = accepted.json()["intake_artifacts"][0]["preparation"]
    assert ready["clinically_segmented"] is False
    assert ready["fdi_assigned"] is False
    assert ready["clinical_axes"] is False
    reopened = InMemoryCaseStore(tmp_path / "cases.json").get(created["id"])
    assert reopened is not None
    assert reopened.intake_artifacts[0]["sha256"] == hashlib.sha256(before).hexdigest()
    assert reopened.intake_artifacts[0]["preparation"]["readiness"] == ready["readiness"]
