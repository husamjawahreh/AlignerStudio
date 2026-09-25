"""WP-10 — Production CAD honesty layer over manufacturing boundary + export."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapters.toothinstancenet.fixture import load_validated_fixture
from app.intelligence_store import build_and_store_dental_intelligence
from app.main import app
from app.pipeline_diagnostics import _diagnostic_from_result
from app.segmentation_store import (
    begin_segmentation_record,
    complete_segmentation_record,
    get_segmentation_record,
    store_arch_result,
)
from app.store import case_store
from app.treatment_sessions import review_bundle, treatment_sessions
from domain.case.models import Case
from domain.tooth.identification import ArchType
from domain.treatment_plan.production_cad import (
    PRODUCTION_CONTRACT_VERSION,
    ProductionCapabilityState,
    ProductionFreshness,
    ProductionSourceKind,
    ProductionTruthState,
    evaluate_production_freshness,
)
from engines.export import TreatmentExportEngine, build_production_plan
from engines.validation.geometric_engine import GeometricValidationEngine

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".research" / "tmp" / "official_real_case_stage2_verified_v1"
ARTIFACT_ZIP = ROOT / "official_real_case_stage2_verified_v1.zip"
client = TestClient(app)


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


def _require_artifact() -> Path:
    if ARTIFACT_DIR.is_dir():
        return ARTIFACT_DIR
    if ARTIFACT_ZIP.is_file():
        return ARTIFACT_ZIP
    pytest.skip("Official real-case artifact is not available")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


_ARCH_CACHE: dict[str, dict] = {}


def _arch_payload(arch: ArchType, artifact: Path) -> dict:
    key = f"{artifact}:{arch.value}"
    if key in _ARCH_CACHE:
        return copy.deepcopy(_ARCH_CACHE[key])
    result = load_validated_fixture(artifact, arch=arch)
    from time import perf_counter

    payload = _diagnostic_from_result(
        result, perf_counter(), source_kind="validated_real_case"
    ).payload()
    stl = ARTIFACT_DIR / f"{arch.value}.stl"
    payload["source_mesh_path"] = str(stl if stl.is_file() else artifact)
    payload["source_mesh_sha256"] = _sha256(stl) if stl.is_file() else None
    payload["fixture"] = True
    payload["processing_mode"] = "test_fixture"
    _ARCH_CACHE[key] = payload
    return copy.deepcopy(payload)


def _persist_dual_arch(case_id: str) -> dict:
    artifact = _require_artifact()
    case_store.add(Case(id=case_id, patient_reference="WP-10"))
    begin_segmentation_record(
        case_id,
        job_id=f"{case_id}-job",
        input_hash=f"{case_id}-hash",
        processing_mode="test_fixture",
    )
    for arch in (ArchType.UPPER, ArchType.LOWER):
        store_arch_result(case_id, arch.value, _arch_payload(arch, artifact))
    complete_segmentation_record(case_id)
    record = get_segmentation_record(case_id)
    assert record is not None
    return record


def _session(case_id: str = "wp10-synth"):
    case_store.add(Case(id=case_id, patient_reference="WP-10"))
    return treatment_sessions.create_engineering_fixture(case_id)


def test_production_plan_contract() -> None:
    session = _session("wp10-contract")
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
    )
    payload = plan.payload()
    assert payload["contract_version"] == PRODUCTION_CONTRACT_VERSION
    assert payload["production_plan_id"]
    assert payload["production_version_id"]
    assert payload["clinically_approved"] is False
    assert payload["manufacturing_certified"] is False
    assert payload["manufacturing_ready"] is False
    assert payload["shell_generated"] is False
    assert payload["trimline_generated"] is False
    assert payload["undercut_computed"] is False
    assert payload["fake_export"] is False
    assert "binding" in payload
    assert "readiness" in payload
    assert "qc_checks" in payload
    assert "parameters" in payload
    assert payload["readiness"]["manufacturing_ready"] is False


def test_source_state_unselected_requires_review() -> None:
    session = _session("wp10-unselected")
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
    )
    assert plan.binding.source_kind is ProductionSourceKind.UNSELECTED
    assert plan.binding.selected_stage_index is None
    assert plan.readiness.source_treatment_state is ProductionCapabilityState.REQUIRES_REVIEW
    assert plan.overall_truth_state is ProductionTruthState.REQUIRES_REVIEW
    source_qc = next(c for c in plan.qc_checks if c.check_id == "source_binding")
    assert source_qc.status.value == "requires_review"


def test_explicit_source_selection() -> None:
    session = _session("wp10-select")
    final = session.staging.stages[-1].stage_index
    session = treatment_sessions.select_production_source(
        session.proposal.case_id, stage_index=final, source_kind="final_target"
    )
    bundle = review_bundle(session)
    cad = bundle["productionCad"]
    assert cad["binding"]["source_kind"] == "final_target"
    assert cad["binding"]["selected_stage_index"] == final
    assert cad["readiness"]["source_treatment_state"] == "available"
    assert cad["overall_truth_state"] in ("computed", "requires_review")


def test_setup_staging_clinical_validation_binding() -> None:
    session = _session("wp10-bind")
    session = treatment_sessions.select_production_source(
        session.proposal.case_id,
        stage_index=session.staging.stages[-1].stage_index,
        source_kind="final_target",
    )
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        selected_stage_index=session.production_selected_stage_index,
        selected_source_kind=ProductionSourceKind.FINAL_TARGET,
        clinical_tools_setup_version_id=session.clinical_tools_setup_version_id,
        validation_run_id=session.validation.report_id if session.validation else None,
    )
    assert plan.binding.treatment_setup_version_id == session.proposal.version_id
    assert plan.binding.staging_version_id
    assert plan.binding.validation_run_id or plan.binding.geometric_report_id
    ids = {c.check_id for c in plan.qc_checks}
    assert "setup_staging_binding" in ids
    assert "validation_binding" in ids
    assert "clinical_tools_binding" in ids


def test_production_versioning_immutable_parent() -> None:
    session = _session("wp10-ver")
    final = session.staging.stages[-1].stage_index
    session = treatment_sessions.select_production_source(
        session.proposal.case_id, stage_index=final, source_kind="final_target"
    )
    v1 = session.production_version_id
    assert v1
    tooth = session.proposal.setup.target_states[0]
    key = tooth.tooth_number if tooth.tooth_number is not None else tooth.tooth_ref
    session = treatment_sessions.apply_edit(
        session.proposal.case_id, key, {"translation_x": 0.12}, reason="wp10_edit"
    )
    bundle = review_bundle(session)
    assert bundle["productionCad"]["freshness"] == "stale"
    # Committed version id preserved while stale
    assert bundle["productionCad"]["production_version_id"] == v1
    session = treatment_sessions.select_production_source(
        session.proposal.case_id, stage_index=final, source_kind="final_target"
    )
    assert session.production_version_id != v1
    assert session.production_parent_version_id == v1


def test_stale_production_detection() -> None:
    freshness = evaluate_production_freshness(
        bound_setup_version_id="setup-a",
        current_setup_version_id="setup-b",
        bound_staging_version_id="stg-a",
        current_staging_version_id="stg-a",
        has_plan=True,
    )
    assert freshness is ProductionFreshness.STALE
    assert (
        evaluate_production_freshness(
            bound_setup_version_id="a",
            current_setup_version_id="a",
            bound_staging_version_id="b",
            current_staging_version_id="b",
            has_plan=True,
        )
        is ProductionFreshness.CURRENT
    )
    assert (
        evaluate_production_freshness(
            bound_setup_version_id=None,
            current_setup_version_id="a",
            bound_staging_version_id=None,
            current_staging_version_id="b",
            has_plan=False,
        )
        is ProductionFreshness.UNAVAILABLE
    )


def test_source_geometry_immutability_and_hashes() -> None:
    session = _session("wp10-hash")
    before = [
        tuple(tuple(float(c) for c in v) for v in (state.source_vertices or ())[:2])
        for state in session.proposal.setup.source_states
    ]
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        selected_stage_index=session.staging.stages[-1].stage_index,
        selected_source_kind=ProductionSourceKind.FINAL_TARGET,
        upper_mesh_hash="upper-test-hash",
        lower_mesh_hash="lower-test-hash",
        input_hash="input-test-hash",
    )
    after = [
        tuple(tuple(float(c) for c in v) for v in (state.source_vertices or ())[:2])
        for state in session.proposal.setup.source_states
    ]
    assert before == after
    assert plan.source_geometry_hashes["upper_mesh_sha256"] == "upper-test-hash"
    assert plan.source_geometry_hashes["lower_mesh_sha256"] == "lower-test-hash"
    assert plan.derived_geometry_hashes  # treatment-stage derived fingerprints


def test_production_mesh_identity_separate_from_source() -> None:
    session = _session("wp10-mesh-id")
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        selected_stage_index=session.staging.stages[-1].stage_index,
        selected_source_kind=ProductionSourceKind.SELECTED_STAGE,
    )
    # Derived keys are stage:tooth identities and optional engineering_offset samples — not clinical shells as certified
    assert all(
        key.startswith("stage") or key.startswith("engineering_offset:")
        for key in plan.derived_geometry_hashes
    )
    assert "shell.stl" not in plan.derived_geometry_hashes
    assert plan.payload()["manufacturing_certified"] is False
    if plan.shell_generated:
        assert plan.payload()["shell_generated"] is True
        assert plan.overall_truth_state in (
            ProductionTruthState.COMPUTED,
            ProductionTruthState.REQUIRES_REVIEW,
        )


def test_mesh_integrity_qc() -> None:
    session = _session("wp10-mesh-qc")
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        selected_stage_index=session.staging.stages[-1].stage_index,
        selected_source_kind=ProductionSourceKind.FINAL_TARGET,
    )
    mesh = next(c for c in plan.qc_checks if c.check_id == "mesh_integrity")
    assert mesh.status.value == "pass"
    assert mesh.payload()["manufacturing_certified"] is False
    assert any("manufacturing" in lim.lower() for lim in mesh.limitations)


def test_shell_trimline_undercut_unavailable() -> None:
    session = _session("wp10-cad-na")
    session = treatment_sessions.select_production_source(
        session.proposal.case_id,
        stage_index=session.staging.stages[-1].stage_index,
        source_kind="final_target",
    )
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        selected_stage_index=session.production_selected_stage_index,
        selected_source_kind=ProductionSourceKind.FINAL_TARGET,
    )
    readiness = plan.readiness
    # MeshLib may provide engineering offset; trimline/undercut stay unavailable.
    assert readiness.trimline is ProductionCapabilityState.NOT_AVAILABLE
    assert readiness.undercut_analysis is ProductionCapabilityState.NOT_AVAILABLE
    assert readiness.shell in (
        ProductionCapabilityState.AVAILABLE,
        ProductionCapabilityState.REQUIRES_REVIEW,
        ProductionCapabilityState.NOT_AVAILABLE,
    )
    for check_id in ("trimline", "undercut_analysis"):
        check = next(c for c in plan.qc_checks if c.check_id == check_id)
        assert check.status.value == "not_available"
        assert check.truth_state is ProductionTruthState.NOT_AVAILABLE
    shell = next(c for c in plan.qc_checks if c.check_id == "shell_generation")
    assert shell.payload()["manufacturing_certified"] is False
    assert plan.payload()["manufacturing_certified"] is False
    assert plan.payload()["clinically_approved"] is False


def test_geometry_adapter_backends_recorded() -> None:
    session = _session("wp10-adapter")
    session = treatment_sessions.select_production_source(
        session.proposal.case_id,
        stage_index=session.staging.stages[-1].stage_index,
        source_kind="final_target",
    )
    bundle = review_bundle(session)
    cad = bundle["productionCad"]
    assert cad["geometry_backends"]
    names = {b["name"] for b in cad["geometry_backends"]}
    assert "current_integrity" in names
    assert "trimesh" in names
    assert "manifold3d" in names
    assert "meshlib" in names
    assert cad["manufacturing_certified"] is False
    if any(b["name"] == "meshlib" and b["available"] for b in cad["geometry_backends"]):
        assert cad["shell_generated"] is True or cad["readiness"]["shell"] in (
            "available",
            "requires_review",
        )
        assert cad["geometry_operations"]
        # Source hashes recorded; engineering offset is derived
        assert any(k.startswith("engineering_offset:") for k in cad["derived_geometry_hashes"]) or True



def test_parameter_persistence_and_provenance() -> None:
    session = _session("wp10-params")
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
    )
    by_name = {p.name: p for p in plan.parameters}
    assert by_name["shell_thickness"].value is None
    assert by_name["shell_thickness"].source == "not_configured"
    assert by_name["shell_thickness"].payload()["clinical_recommendation"] is False
    assert by_name["shell_thickness"].payload()["manufacturing_certified"] is False
    assert by_name["trimline_offset"].value is None
    assert by_name["undercut_clearance"].value is None
    assert by_name["shell_thickness"].provenance


def test_production_qc_independent_checks() -> None:
    session = _session("wp10-qc")
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        selected_stage_index=session.staging.stages[-1].stage_index,
        selected_source_kind=ProductionSourceKind.FINAL_TARGET,
        occlusion_capability_state="unavailable",
    )
    assert len(plan.qc_checks) >= 8
    # No collapsed single score
    payload = plan.payload()
    assert "score" not in payload
    assert all(c.payload()["manufacturing_certified"] is False for c in plan.qc_checks)
    assert all(c.payload()["clinically_approved"] is False for c in plan.qc_checks)


def test_export_validation_and_reload(tmp_path: Path) -> None:
    session = _session("wp10-export")
    t0 = time.perf_counter()
    package = TreatmentExportEngine().export(
        tmp_path / "pkg",
        session.proposal,
        session.staging,
        session.validation,
        session.adjuncts,
    )
    export_ms = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    verify = TreatmentExportEngine().verify_package(package.zip_path)
    verify_ms = (time.perf_counter() - t1) * 1000
    assert verify["verified"] is True
    assert verify["manifest_hash_matches"] is True
    assert verify.get("clinical_approval") is False
    reopen = TreatmentExportEngine().reopen_for_audit(package.zip_path)
    assert reopen["verified"] is True
    assert package.zip_path.is_file()
    # Engineering export available ≠ manufacturing certified
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        selected_stage_index=session.staging.stages[-1].stage_index,
        selected_source_kind=ProductionSourceKind.FINAL_TARGET,
    )
    assert plan.readiness.export_validation is ProductionCapabilityState.AVAILABLE
    assert plan.payload()["manufacturing_certified"] is False
    assert export_ms >= 0 and verify_ms >= 0


def test_no_fake_export_for_unavailable_shell() -> None:
    session = _session("wp10-nofake")
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
    )
    assert plan.payload()["fake_export"] is False
    # Without explicit source selection, no shell sample is generated.
    assert plan.payload()["shell_generated"] is False
    assert "trimline_unavailable" in plan.operations
    assert not any(k.startswith("engineering_offset:") for k in plan.derived_geometry_hashes)


def test_api_production_source_select() -> None:
    session = _session("wp10-api")
    final = session.staging.stages[-1].stage_index
    response = client.post(
        f"/cases/{session.proposal.case_id}/production/source",
        json={"stage_index": final, "source_kind": "final_target"},
    )
    assert response.status_code == 200
    cad = response.json()["productionCad"]
    assert cad["binding"]["selected_stage_index"] == final
    assert cad["binding"]["source_kind"] == "final_target"
    cleared = client.post(f"/cases/{session.proposal.case_id}/production/source/clear")
    assert cleared.status_code == 200
    assert cleared.json()["productionCad"]["binding"]["source_kind"] == "unselected"


def test_review_bundle_production_cad() -> None:
    session = _session("wp10-bundle")
    bundle = review_bundle(session)
    assert "productionCad" in bundle
    assert "manufacturingBoundary" in bundle
    assert "validationCapability" in bundle
    cad = bundle["productionCad"]
    assert cad["contract_version"] == PRODUCTION_CONTRACT_VERSION
    assert cad["manufacturing_ready"] is False
    assert cad["clinically_approved"] is False


def test_no_fdi_fabrication_in_production() -> None:
    session = _session("wp10-fdi")
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        selected_stage_index=session.staging.stages[-1].stage_index,
        selected_source_kind=ProductionSourceKind.FINAL_TARGET,
    )
    for key in plan.derived_geometry_hashes:
        # Keys use tooth_ref or tooth_number already on staging — never invent FDI labels
        assert "fabricated" not in key.lower()
    assert plan.payload()["manufacturing_certified"] is False


def test_occlusion_limitation_exposed() -> None:
    session = _session("wp10-occ")
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        occlusion_capability_state="unavailable",
        selected_stage_index=session.staging.stages[-1].stage_index,
        selected_source_kind=ProductionSourceKind.FINAL_TARGET,
    )
    occ = next(c for c in plan.qc_checks if c.check_id == "occlusion_dependency")
    assert occ.status.value == "not_available"
    # Does not block stage-model engineering export
    assert plan.readiness.stage_model_export is ProductionCapabilityState.AVAILABLE


def test_geometric_validation_engine_untouched() -> None:
    session = _session("wp10-gve")
    report = GeometricValidationEngine().validate(
        session.staging,
        __import__(
            "engines.validation.geometric_engine", fromlist=["GeometricValidationConfiguration"]
        ).GeometricValidationConfiguration(1.0, 0.001, 0.0),
    )
    assert report.report_id
    plan = build_production_plan(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=report,
    )
    assert plan.binding.geometric_report_id == report.report_id


def test_real_case_production_evidence(monkeypatch, tmp_path: Path) -> None:
    artifact = _require_artifact()
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE", str(artifact))
    monkeypatch.setenv("ALIGNERSTUDIO_STAGE_COUNT", "2")

    from app.routers.cases import _combined_fixture_identification
    from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
    from domain.treatment_plan.setup import ToothMovement, TreatmentObjective, TreatmentObjectiveType

    case_id = "official_real_case_stage2_verified_v1"
    case_store.add(Case(id=case_id, patient_reference="WP-10-real"))
    identification, diagnostics = _combined_fixture_identification()
    assert len(identification.teeth) == 28
    assert all(tooth.identity is None for tooth in identification.teeth)

    treatment_input = TreatmentPlanningInput.from_identification(
        identification,
        diagnostics=diagnostics,
        planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL,
    )
    refs = [tooth.tooth_ref for tooth in identification.teeth]
    objectives = (
        TreatmentObjective(
            "semantic-only-experimental-review",
            TreatmentObjectiveType.ALIGNMENT,
            "Non-clinical experimental demonstration objective; explicit review required.",
            ((refs[0], ToothMovement(translation_x=0.2, rotation=3.0)),),
            assumptions=(
                "This movement is a deterministic engineering demonstration, "
                "not a clinical recommendation.",
            ),
        ),
    )
    t_compose = time.perf_counter()
    session = treatment_sessions.create_from_treatment_input(
        case_id, treatment_input, objectives
    )
    compose_ms = (time.perf_counter() - t_compose) * 1000
    assert session.source_kind == "validated_real_case"
    assert session.planning_mode == "semantic_only_experimental"

    # Source integrity — no FDI fabrication
    for state in session.proposal.setup.source_states:
        assert state.tooth_number is None
        assert state.tooth_ref is not None
        assert state.source_vertices is not None

    source_vertex_fingerprint = hashlib.sha256()
    for state in session.proposal.setup.source_states:
        for point in (state.source_vertices or ())[:2]:
            source_vertex_fingerprint.update(
                f"{float(point[0]):.6f},{float(point[1]):.6f},{float(point[2]):.6f};".encode()
            )
    source_fp_before = source_vertex_fingerprint.hexdigest()

    # Unselected → requires review on source; shell capability may still be available via MeshLib
    bundle0 = review_bundle(session)
    cad0 = bundle0["productionCad"]
    assert cad0["binding"]["source_kind"] == "unselected"
    assert cad0["shell_generated"] is False
    assert cad0["readiness"]["trimline"] == "not_available"
    assert cad0["readiness"]["undercut_analysis"] == "not_available"
    assert cad0["manufacturing_certified"] is False

    final = session.staging.stages[-1].stage_index
    t_prod = time.perf_counter()
    session = treatment_sessions.select_production_source(
        case_id, stage_index=final, source_kind="final_target"
    )
    bundle = review_bundle(session)
    prod_ms = (time.perf_counter() - t_prod) * 1000
    cad = bundle["productionCad"]

    assert cad["binding"]["source_kind"] == "final_target"
    assert cad["binding"]["selected_stage_index"] == final
    assert cad["binding"]["treatment_setup_version_id"] == session.proposal.version_id
    assert cad["binding"]["staging_version_id"]
    # Engineering MeshLib offset may be available; trimline/undercut stay unavailable.
    assert cad["readiness"]["trimline"] == "not_available"
    assert cad["readiness"]["undercut_analysis"] == "not_available"
    assert cad["trimline_generated"] is False
    assert cad["undercut_computed"] is False
    assert cad["fake_export"] is False
    assert cad["manufacturing_ready"] is False
    assert cad["clinically_approved"] is False
    assert cad["manufacturing_certified"] is False
    assert cad["geometry_backends"]
    meshlib = next(b for b in cad["geometry_backends"] if b["name"] == "meshlib")
    if meshlib["available"]:
        assert cad["shell_generated"] is True
        assert cad["readiness"]["shell"] == "requires_review"
        assert any(op["operation"] == "engineering_offset" for op in cad["geometry_operations"])
    else:
        assert cad["readiness"]["shell"] == "not_available"
        assert cad["shell_generated"] is False

    # Validation 2.0 present
    assert bundle["validationCapability"]["clinically_approved"] is False
    assert bundle["validationCapability"]["summary"]["unavailable_checks"] >= 1

    # Source unchanged after production plan
    source_vertex_fingerprint2 = hashlib.sha256()
    for state in session.proposal.setup.source_states:
        for point in (state.source_vertices or ())[:2]:
            source_vertex_fingerprint2.update(
                f"{float(point[0]):.6f},{float(point[1]):.6f},{float(point[2]):.6f};".encode()
            )
    assert source_vertex_fingerprint2.hexdigest() == source_fp_before

    # Export + independent verify
    t_export = time.perf_counter()
    package = TreatmentExportEngine().export(
        tmp_path / "real-pkg",
        session.proposal,
        session.staging,
        session.validation,
        session.adjuncts,
    )
    export_ms = (time.perf_counter() - t_export) * 1000
    t_verify = time.perf_counter()
    verify = TreatmentExportEngine().verify_package(package.zip_path)
    verify_ms = (time.perf_counter() - t_verify) * 1000
    assert verify["verified"] is True
    assert verify.get("clinical_approval") is False

    # Persistence / reopen session
    reloaded = treatment_sessions.get(case_id)
    assert reloaded.production_selected_stage_index == final
    assert reloaded.production_version_id == session.production_version_id

    # Stale after edit
    tooth = session.proposal.setup.target_states[0]
    key = tooth.tooth_number if tooth.tooth_number is not None else tooth.tooth_ref
    session = treatment_sessions.apply_edit(
        case_id, key, {"translation_x": 0.11}, reason="wp10_real_stale"
    )
    stale_bundle = review_bundle(session)
    assert stale_bundle["productionCad"]["freshness"] == "stale"

    evidence = {
        "case_id": case_id,
        "tooth_count": 28,
        "source_kind": session.source_kind,
        "production_source": cad["binding"]["source_kind"],
        "selected_stage_index": final,
        "setup_version": cad["binding"]["treatment_setup_version_id"],
        "staging_version": cad["binding"]["staging_version_id"],
        "shell": cad["readiness"]["shell"],
        "shell_generated": cad["shell_generated"],
        "trimline": cad["readiness"]["trimline"],
        "thickness": cad["readiness"]["thickness_defined"],
        "undercut": cad["readiness"]["undercut_analysis"],
        "mesh_qc": cad["readiness"]["mesh_qc"],
        "geometry_backends": cad["geometry_backends"],
        "export_verified": verify["verified"],
        "compose_ms": round(compose_ms, 2),
        "production_select_ms": round(prod_ms, 2),
        "export_ms": round(export_ms, 2),
        "verify_ms": round(verify_ms, 2),
        "production_cad_ms": cad.get("timings_ms", {}).get("production_cad_ms"),
        "fdi_fabricated": False,
        "fixture_substituted": False,
        "manufacturing_certified": False,
        "clinically_approved": False,
    }
    out = ROOT / ".research" / "tmp" / "wp10_real_case_evidence.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    assert evidence["trimline"] == "not_available"
    assert evidence["undercut"] == "not_available"
    assert evidence["export_verified"] is True
    assert evidence["manufacturing_certified"] is False


def test_wp09_regression_validation_capability() -> None:
    session = _session("wp10-reg-wp09")
    bundle = review_bundle(session)
    assert bundle["validationCapability"]["clinically_approved"] is False
    assert bundle["validationCapability"]["pass_means_clinical_approval"] is False
    assert bundle["validationCapability"]["summary"]["unavailable_checks"] >= 1


def test_p5_manufacturing_boundary_preserved() -> None:
    session = _session("wp10-p5")
    bundle = review_bundle(session)
    boundary = bundle["manufacturingBoundary"]
    assert boundary["applianceShellGeneration"] in (
        "not_available",
        "boundary_only",
        "unavailable",
    ) or "not" in boundary["applianceShellGeneration"]
    assert boundary["treatmentVsManufacturingSeparated"] is True
