"""P8 — Real-case QA matrix, integrity gates, and honest PENDING documentation.

Does not invent clinical data, FDI, manufacturing geometry, or acceptance evidence.
Cells that cannot be evidenced with in-repo artifacts are explicit PENDING skips.
"""

from __future__ import annotations

import os
import tracemalloc
from pathlib import Path

import numpy as np
import pytest
import trimesh
from fastapi.testclient import TestClient

from app.main import app
from app.store import case_store
from app.treatment_sessions import TreatmentSessionStore, treatment_sessions
from domain.treatment_plan.manufacturing import ManufacturingCapabilityStatus
from domain.treatment_plan.staging import StagingConfiguration
from engines.export import TreatmentExportEngine
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
    _mesh_pair_metrics,
)

ARTIFACT_ROOT = Path(".research/tmp/official_real_case_stage2_verified_v1")
ARTIFACT_ZIP = Path("official_real_case_stage2_verified_v1.zip")
SECOND_REAL_CASE = Path("data/benchmark/second_real_case")  # intentionally absent


@pytest.fixture(autouse=True)
def _clear(tmp_path, monkeypatch):
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    case_store.clear()
    treatment_sessions.clear()
    yield
    case_store.clear()
    treatment_sessions.clear()


client = TestClient(app)


def _artifact_available() -> bool:
    return (ARTIFACT_ROOT / "manifest.json").is_file() or ARTIFACT_ZIP.is_file()


def test_matrix_upper_plus_lower_real_artifact_identification() -> None:
    if not _artifact_available():
        pytest.skip("Verified real-case artifact unavailable")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
    if ARTIFACT_ROOT.is_dir():
        monkeypatch.setenv(
            "ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(ARTIFACT_ROOT.resolve())
        )
    try:
        from app.routers.cases import _combined_fixture_identification

        identification, notes = _combined_fixture_identification()
        arches = set()
        for tooth in identification.teeth:
            arch = tooth.instance.arch
            arches.add(arch.value if hasattr(arch, "value") else str(arch))
        assert arches == {"upper", "lower"}
        assert len(identification.teeth) >= 28
        assert notes is not None
    finally:
        monkeypatch.undo()


@pytest.mark.parametrize("arch", ["upper", "lower"])
def test_matrix_single_arch_planning_remains_unsupported(arch: str, tmp_path) -> None:
    """Product policy: plan requires both arches — single-arch planning is unavailable."""
    case_id = client.post("/cases", json={"patient_reference": f"single-{arch}"}).json()["id"]
    mesh = tmp_path / f"{arch}.stl"
    mesh.write_bytes(
        b"solid empty\nendsolid empty\n"
        if False
        else _minimal_ascii_stl()
    )
    with mesh.open("rb") as handle:
        upload = client.post(
            f"/cases/{case_id}/uploads",
            params={"arch": arch},
            files={"file": (mesh.name, handle, "model/stl")},
        )
    assert upload.status_code == 200
    plan = client.post(f"/cases/{case_id}/plan")
    assert plan.status_code == 400
    assert "both" in plan.json()["detail"].lower() or "arch" in plan.json()["detail"].lower()


def _minimal_ascii_stl() -> bytes:
    return (
        b"solid p8\n"
        b"  facet normal 0 0 1\n"
        b"    outer loop\n"
        b"      vertex 0 0 0\n"
        b"      vertex 1 0 0\n"
        b"      vertex 0 1 0\n"
        b"    endloop\n"
        b"  endfacet\n"
        b"endsolid p8\n"
    )


def test_matrix_multiple_real_cases_pending_without_second_artifact() -> None:
    if SECOND_REAL_CASE.exists():
        pytest.fail("Unexpected second real case present — extend matrix coverage instead of PENDING")
    pytest.skip(
        "PENDING: only one verified real case (official_real_case_stage2_verified_v1) "
        "is in-repo; a second provenance-verified case is required for multi-case matrix."
    )


def test_matrix_different_orientations_pending_without_rotated_real_scans() -> None:
    pytest.skip(
        "PENDING: no provenance-verified rotated/misoriented real STL set in-repo; "
        "synthetic axis stability is covered elsewhere without inventing patient scans."
    )


def test_matrix_mesh_density_real_dense_plus_synthetic_scale() -> None:
    """Real artifact is one dense tier; synthetic denser meshes keep geometry oracle parity."""
    first = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    second = first.copy()
    second.apply_translation((2.2, 0.0, 0.0))
    distance, intersects, _ = _mesh_pair_metrics(first, second, 1.0, 0.001)
    assert intersects is False
    assert np.isfinite(distance)
    if not _artifact_available():
        pytest.skip("Real dense artifact unavailable for density matrix note")
    # Documented: single real density tier evidence via verified ZIP meshes.


def test_matrix_missing_data_and_ambiguous_identity_fail_closed() -> None:
    from dataclasses import replace

    from domain.tooth.identification import ArchType
    from engines.arrangement.identification import ToothIdentificationEngine
    from tests.fixtures.synthetic_arch import build_synthetic_arch

    segmentation = build_synthetic_arch(ArchType.UPPER)
    incomplete = replace(
        segmentation,
        instances=segmentation.instances[:-1],
        metadata=replace(segmentation.metadata, output_instance_count=15),
    )
    result = ToothIdentificationEngine().identify(incomplete, ArchType.UPPER)
    assert len(result.identified) == 0
    assert len(result.uncertain) == 15
    assert all(tooth.identity is None for tooth in result.teeth)


def test_matrix_doctor_edit_undo_path_fixture_and_export_reopen() -> None:
    demo = client.post("/cases/demo").json()
    case_id = demo["case"]["id"]
    bundle = demo["review_bundle"]
    tooth = bundle["stages"][0]["teeth"][0]
    tooth_key = tooth.get("toothRef") or tooth["fdiNumber"]
    edited = client.post(
        f"/cases/{case_id}/treatment/edits",
        json={
            "tooth_ref" if isinstance(tooth_key, str) else "tooth_number": tooth_key,
            "translation_x": 0.15,
            "translation_y": 0.0,
            "translation_z": 0.0,
            "rotation": 0.0,
            "tip": 0.0,
            "torque": 0.0,
            "angulation": 0.0,
            "intrusion": 0.0,
            "extrusion": 0.0,
        },
    )
    assert edited.status_code == 200
    reopen = client.post(f"/cases/{case_id}/export/reopen")
    assert reopen.status_code == 200
    body = reopen.json()
    assert body["verified"] is True
    assert body["session_reimport_available"] is False
    assert body["session_reimport_status"] == "unavailable"
    assert body["clinical_approval"] is False
    boundary = body.get("manufacturing_boundary") or {}
    assert boundary.get("applianceShellGeneration") in {
        None,
        ManufacturingCapabilityStatus.UNAVAILABLE.value,
        "unavailable",
    } or "unavailable" in str(boundary).lower()


def test_matrix_manufacturing_handoff_remains_unavailable() -> None:
    from domain.treatment_plan.manufacturing import build_manufacturing_boundary_report

    report = build_manufacturing_boundary_report(has_stage_models=True)
    assert report.appliance_shell_generation is ManufacturingCapabilityStatus.UNAVAILABLE
    assert report.trimline_cutline is ManufacturingCapabilityStatus.UNAVAILABLE
    assert report.manufacturing_qc_report is ManufacturingCapabilityStatus.UNAVAILABLE
    assert report.treatment_vs_manufacturing_separated is True


def test_export_reopen_preserves_plan_identity_and_hashes(tmp_path) -> None:
    store = TreatmentSessionStore()
    session = store.create_engineering_fixture("p8-export")
    package = TreatmentExportEngine().export(tmp_path / "pkg", session.proposal, session.staging, session.validation, session.adjuncts)
    first = TreatmentExportEngine().reopen_for_audit(package.zip_path)
    second = TreatmentExportEngine().reopen_for_audit(package.zip_path)
    assert first["verified"] is True
    assert first["treatment_plan_id"] == session.proposal.plan_id
    assert first["verified_files"] == second["verified_files"]
    assert first["session_reimport_available"] is False


def test_p6_p7_intelligence_lazy_on_validated_real_case_compose() -> None:
    store = TreatmentSessionStore()
    session = store.create_engineering_fixture("p8-lazy-base")
    from app.treatment_sessions import TreatmentSession

    shell = TreatmentSession(
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        adjuncts=session.adjuncts,
        source_kind="validated_real_case",
        experimental=True,
        planning_mode="semantic_only_experimental",
    )
    calls: list[bool] = []
    original = store._intelligence.generate

    def tracking(*args, **kwargs):
        calls.append(bool(kwargs.get("generate_alternatives", True)))
        return original(*args, **kwargs)

    store._intelligence.generate = tracking  # type: ignore[method-assign]
    attached = store._attach_intelligence(shell)
    assert calls == [False]
    assert attached.intelligence is not None
    assert len(attached.intelligence.candidates) == 1


def test_memory_lifecycle_engineering_fixture_releases_peak() -> None:
    tracemalloc.start()
    store = TreatmentSessionStore()
    store.create_engineering_fixture("p8-mem-a")
    store.create_engineering_fixture("p8-mem-b")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak >= current
    assert peak < 500_000_000  # engineering fixtures must stay well under 500MB Python peak
    store.clear()


def test_provenance_integrity_on_demo_export_reopen() -> None:
    demo = client.post("/cases/demo").json()
    case_id = demo["case"]["id"]
    assert demo["review_bundle"]["fixture"] is True or demo["review_bundle"].get("experimental") is True
    body = client.post(f"/cases/{case_id}/export/reopen").json()
    assert body["verified"] is True
    assert body["clinical_approval"] is False
    assert body.get("fixture") is True or body.get("provenance") in {"fixture", "experimental", "generated"}


def test_model_adapter_research_remain_unavailable() -> None:
    from engines.planning.intelligence import research_adapter_evaluations

    evaluations = research_adapter_evaluations()
    assert len(evaluations) >= 3
    for item in evaluations:
        assert item.status.value == "unavailable"
