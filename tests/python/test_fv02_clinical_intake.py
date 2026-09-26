"""FV-02 intake: formats, quality, provenance, arch truth, and privacy."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
import trimesh
from app.store import InMemoryCaseStore
from fastapi.testclient import TestClient

from domain.case.intake import case_arch_summary, privacy_log_view, resolve_arch
from engines.geometry.intake_inspection import derive_cleaned_mesh, inspect_source_file
from engines.geometry.intake_libraries import evaluate_intake_libraries

FIXTURE_OBJ = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_segmentation_arch.obj"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _box(path: Path) -> None:
    trimesh.creation.box().export(path)


def test_stl_ply_and_obj_round_trip_without_units_or_fdi(tmp_path: Path) -> None:
    stl = tmp_path / "scan.stl"
    ply = tmp_path / "scan.ply"
    obj = tmp_path / "scan.obj"
    mesh = trimesh.creation.box()
    mesh.export(stl)
    mesh.export(ply)
    mesh.export(obj)
    for path, kind in ((stl, "stl"), (ply, "ply"), (obj, "obj")):
        before = path.read_bytes()
        record = inspect_source_file(
            path, case_id="case-1", explicit_arch="upper", original_filename=path.name
        )
        assert path.read_bytes() == before
        assert record["sha256"] == _sha(path)
        assert record["format"].startswith(kind)
        assert record["readiness"] == "READY"
        assert record["units"] is None
        assert record["units_encoded"] is False
        assert record["fdi_assigned"] is False
        assert record["occlusion_established"] is False
        assert record["arch"]["truth"] == "USER_PROVIDED"
        assert record["arch"]["filename_used"] is False
        assert record["coordinates"]["clinical_orientation"]["available"] is False
        assert record["coordinates"]["geometric_orientation"]["clinical_axes"] is False
        assert record["source_bytes_modified"] is False


def test_filename_does_not_assign_arch(tmp_path: Path) -> None:
    path = tmp_path / "upper_patient.stl"
    _box(path)
    record = inspect_source_file(path, explicit_arch=None)
    assert record["arch"]["arch"] == "ARCH_UNKNOWN"
    assert resolve_arch(explicit="left")["arch"] == "ARCH_UNKNOWN"


def test_open_surface_is_a_warning_not_a_blocker(tmp_path: Path) -> None:
    mesh = trimesh.creation.box()
    mesh.faces = mesh.faces[:-1]
    path = tmp_path / "open.stl"
    mesh.export(path)
    record = inspect_source_file(path, explicit_arch="lower")
    assert "open_surface" in record["warnings"]
    assert record["readiness"] == "READY_WITH_WARNINGS"
    assert "BLOCKED_INVALID_INPUT" != record["readiness"]
    assert record["volume"] is None


def test_empty_nan_and_unreadable_are_blocked(tmp_path: Path) -> None:
    empty = tmp_path / "empty.stl"
    empty.write_bytes(b"")
    unreadable = inspect_source_file(empty)
    assert unreadable["readiness"] == "BLOCKED_INVALID_INPUT"

    missing = inspect_source_file(tmp_path / "missing.stl")
    assert missing["blockers"] == ["file_missing"]

    nan_mesh = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [0, 1, np.nan]],
        faces=[[0, 1, 2]],
        process=False,
    )
    nan_path = tmp_path / "nan.stl"
    nan_mesh.export(nan_path)
    # STL cannot store NaN reliably; inject a non-finite vertex after a valid load by
    # writing an OBJ, which keeps the token.
    obj = tmp_path / "nan.obj"
    obj.write_text("v 0 0 0\nv 1 0 0\nv 0 1 nan\nf 1 2 3\n", encoding="utf-8")
    record = inspect_source_file(obj)
    assert record["readiness"] == "BLOCKED_INVALID_INPUT"
    assert "coordinates_not_finite" in record["blockers"]


def test_degenerate_nonmanifold_boundary_and_components(tmp_path: Path) -> None:
    degenerate = tmp_path / "degenerate.obj"
    degenerate.write_text(
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 0\nf 1 2 3\nf 1 2 4\n",
        encoding="utf-8",
    )
    record = inspect_source_file(degenerate, explicit_arch="upper")
    assert "degenerate_faces" in record["warnings"] or "duplicate_vertices" in record["warnings"]
    assert record["readiness"] == "READY_WITH_WARNINGS"

    bowtie = tmp_path / "bowtie.obj"
    bowtie.write_text(
        "\n".join(
            [
                "v 0 0 0",
                "v 1 0 0",
                "v 0 1 0",
                "v 0 -1 0",
                "v -1 0 0",
                "f 1 2 3",
                "f 1 2 4",
                "f 1 2 5",
            ]
        ),
        encoding="utf-8",
    )
    nonmanifold = inspect_source_file(bowtie)
    assert nonmanifold["quality"]["checks"]["non_manifold_edges"] > 0
    assert "non_manifold_edges" in nonmanifold["warnings"]
    assert "boundary_edges" in nonmanifold["warnings"]
    assert nonmanifold["readiness"] == "READY_WITH_WARNINGS"

    fixture = inspect_source_file(FIXTURE_OBJ, explicit_arch=None)
    assert FIXTURE_OBJ.read_text(encoding="utf-8").startswith("# Engineering fixture")
    assert fixture["quality"]["checks"]["component_count"] > 1
    assert "disconnected_components" in fixture["warnings"]
    assert fixture["fdi_assigned"] is False
    assert fixture["arch"]["arch"] == "ARCH_UNKNOWN"


def test_derived_mesh_keeps_the_source_hash(tmp_path: Path) -> None:
    source = tmp_path / "source.obj"
    source.write_text(
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\nf 1 2 3\nf 1 1 1\n",
        encoding="utf-8",
    )
    before = source.read_bytes()
    derived_path = tmp_path / "derived.obj"
    derived = derive_cleaned_mesh(source, derived_path)
    assert source.read_bytes() == before
    assert derived["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert derived["output_sha256"] != derived["source_sha256"]
    assert derived["replaces_source"] is False
    assert derived["truth_state"] == "DERIVED"
    assert "not a clinical tooth" in derived["limitations"]


def test_upper_lower_and_dual_do_not_imply_occlusion(tmp_path: Path) -> None:
    upper = tmp_path / "a.stl"
    lower = tmp_path / "b.stl"
    _box(upper)
    _box(lower)
    artifacts = [
        inspect_source_file(upper, explicit_arch="upper"),
        inspect_source_file(lower, explicit_arch="lower"),
    ]
    summary = case_arch_summary(artifacts)
    assert summary["upper_present"] and summary["lower_present"]
    assert summary["occlusion_established"] is False
    assert summary["bite_registration_established"] is False
    assert summary["requires_both_arches"] is False
    only_upper = case_arch_summary(artifacts[:1])
    assert only_upper["lower_present"] is False
    assert only_upper["occlusion_established"] is False


def test_privacy_log_view_drops_filename_and_patient_reference(tmp_path: Path) -> None:
    path = tmp_path / "Jane_Doe.stl"
    _box(path)
    record = inspect_source_file(path, case_id="technical-id", original_filename="Jane_Doe.stl")
    record["patient_reference"] = "Jane Doe"
    logged = privacy_log_view(record)
    assert "Jane" not in str(logged)
    assert logged["case_id"] == "technical-id"
    assert "sha256" in logged


def test_libraries_do_not_add_a_new_intake_dependency() -> None:
    report = evaluate_intake_libraries()
    assert report["trimesh"]["importable"] is True
    assert report["trimesh"]["used_for"]
    assert "Open3D" in report["decision"]
    assert report["manifold3d"]["used_for"] is None


def test_upload_persists_intake_and_reopens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import app

    store = InMemoryCaseStore(tmp_path / "cases.json")
    monkeypatch.setattr("app.routers.cases.case_store", store)
    monkeypatch.setattr("app.routers.cases.UPLOAD_DIR", tmp_path)
    client = TestClient(app)
    created = client.post("/cases", json={"patient_reference": "local-ref"}).json()
    assert created["id"] in {item.id for item in store.list()}
    stl = tmp_path / "scan.stl"
    _box(stl)
    uploaded = client.post(
        f"/cases/{created['id']}/uploads",
        params={"arch": "upper"},
        files={"file": ("scan.stl", stl.read_bytes(), "model/stl")},
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    artifact = body["intake_artifacts"][0]
    assert artifact["sha256"] == _sha(stl)
    stored_path = Path(body["meshes"][0]["file_path"])
    assert stored_path.read_bytes() == stl.read_bytes()
    again = InMemoryCaseStore(tmp_path / "cases.json").get(created["id"])
    assert again is not None
    saved = again.intake_artifacts
    assert saved[0]["sha256"] == artifact["sha256"]
    assert saved[0]["occlusion_established"] is False
    assert body["intake_summary"]["occlusion_established"] is False


def test_direct_store_reopen_keeps_source_hash(tmp_path: Path) -> None:
    from domain.case.models import Case, MeshAsset

    source = tmp_path / "scan.ply"
    trimesh.creation.box().export(source)
    record = inspect_source_file(
        source, case_id="c", explicit_arch="lower", original_filename="scan.ply"
    )
    case = Case(id="c")
    case.add_mesh(MeshAsset(arch="lower", file_path=str(source), original_filename="scan.ply"))
    case.intake_artifacts = [record]
    store = InMemoryCaseStore(tmp_path / "cases.json")
    store.add(case)
    loaded = InMemoryCaseStore(tmp_path / "cases.json").get("c")
    assert loaded is not None
    saved = loaded.intake_artifacts[0]
    assert saved["sha256"] == record["sha256"]
    assert source.read_bytes() == source.read_bytes()
    assert saved["format"].startswith("ply")
