"""WP-09 — Validation 2.0 honesty layer over GeometricValidationEngine."""

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
from domain.treatment_plan.validation_v2 import (
    VALIDATION_CONTRACT_VERSION,
    ValidationCategory,
    ValidationCheckState,
    ValidationFreshness,
    ValidationTruthState,
    evaluate_validation_freshness,
)
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)
from engines.validation.validation_v2_engine import build_validation_run

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".research" / "tmp" / "official_real_case_stage2_verified_v1"
ARTIFACT_ZIP = ROOT / "official_real_case_stage2_verified_v1.zip"
client = TestClient(app)
DEFAULT_CONFIG = GeometricValidationConfiguration(1.0, 0.001, 0.0)


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
    case_store.add(Case(id=case_id, patient_reference="WP-09"))
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


def _session(case_id: str = "wp09-synth"):
    case_store.add(Case(id=case_id, patient_reference="WP-09"))
    return treatment_sessions.create_engineering_fixture(case_id)


def test_validation_run_contract() -> None:
    session = _session("wp09-contract")
    run = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        configuration=DEFAULT_CONFIG,
        setup_version_id=session.proposal.version_id,
        occlusion_capability_state="unavailable",
        root_geometry_state="not_available",
        clinical_axes_state="not_available",
        landmark_state="not_available",
    )
    payload = run.payload()
    assert payload["contract_version"] == VALIDATION_CONTRACT_VERSION
    assert payload["validation_run_id"]
    assert payload["clinically_approved"] is False
    assert payload["clinical_safety_guarantee"] is False
    assert payload["pass_means_clinical_approval"] is False
    assert payload["summary"]["validation_score"] is None
    assert payload["geometric_engine_version"] == DEFAULT_CONFIG.engine_version


def test_finding_severity_and_truth_states() -> None:
    session = _session("wp09-findings")
    run = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        configuration=DEFAULT_CONFIG,
        setup_version_id=session.proposal.version_id,
        occlusion_capability_state="unavailable",
        root_geometry_state="not_available",
        clinical_axes_state="not_available",
        landmark_state="not_available",
    )
    assert any(c.category is ValidationCategory.COLLISION for c in run.checks)
    for finding in run.findings:
        assert finding.clinical_interpretation is None
        assert finding.payload()["clinical_diagnosis"] is None
        assert finding.truth_state in (
            ValidationTruthState.COMPUTED,
            ValidationTruthState.NOT_AVAILABLE,
            ValidationTruthState.REQUIRES_REVIEW,
        )
        # Never auto-verified from engine run
        assert finding.truth_state is not ValidationTruthState.VERIFIED


def test_pass_vs_not_available_and_clinical_approval() -> None:
    session = _session("wp09-pass")
    run = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        configuration=DEFAULT_CONFIG,
        setup_version_id=session.proposal.version_id,
        occlusion_capability_state="unavailable",
        root_geometry_state="not_available",
        clinical_axes_state="not_available",
        landmark_state="not_available",
    )
    geometric_pass = [
        c
        for c in run.checks
        if c.category
        in (
            ValidationCategory.COLLISION,
            ValidationCategory.PROXIMITY,
            ValidationCategory.CONTACT,
        )
        and c.check_state is ValidationCheckState.PASS
    ]
    unavailable = [
        c for c in run.checks if c.check_state is ValidationCheckState.NOT_AVAILABLE
    ]
    assert unavailable, "Unavailable capability checks must remain visible"
    assert any(c.category is ValidationCategory.OCCLUSION_CAPABILITY for c in unavailable)
    assert any(c.category is ValidationCategory.ROOT_ANATOMY for c in unavailable)
    assert any(c.category is ValidationCategory.CLINICAL_AXES for c in unavailable)
    assert any(c.category is ValidationCategory.LANDMARKS for c in unavailable)
    assert any(c.category is ValidationCategory.MANUFACTURING_READINESS for c in unavailable)
    # Overall must not collapse to PASS when unavailable checks exist alongside geometric PASS
    if geometric_pass:
        assert run.overall_check_state is not ValidationCheckState.PASS
    assert run.payload()["clinically_approved"] is False


def test_unavailable_occlusion_never_pass() -> None:
    session = _session("wp09-occ")
    run = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        configuration=DEFAULT_CONFIG,
        occlusion_capability_state="unavailable",
    )
    occ = next(c for c in run.checks if c.category is ValidationCategory.OCCLUSION_CAPABILITY)
    assert occ.check_state is ValidationCheckState.NOT_AVAILABLE
    assert occ.truth_state is ValidationTruthState.NOT_AVAILABLE


def test_version_binding_and_staleness() -> None:
    freshness = evaluate_validation_freshness(
        bound_setup_version_id="setup-a",
        current_setup_version_id="setup-b",
        bound_staging_version_id="stg-a",
        current_staging_version_id="stg-a",
        has_run=True,
    )
    assert freshness is ValidationFreshness.STALE

    session = _session("wp09-stale")
    first = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        configuration=DEFAULT_CONFIG,
        setup_version_id="setup-a",
        staging_version_id="stg-a",
    )
    stale = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        configuration=DEFAULT_CONFIG,
        setup_version_id="setup-b",
        staging_version_id="stg-a",
        current_setup_version_id="setup-b",
        current_staging_version_id="stg-a",
        previous_run=first,
    )
    assert stale.freshness is ValidationFreshness.STALE


def test_post_edit_revalidation() -> None:
    session = _session("wp09-edit")
    before = review_bundle(session)
    assert before["validationCapability"]["freshness"] == "current"
    before_setup = before["validationCapability"]["binding"]["setup_version_id"]
    tooth = session.proposal.setup.target_states[0]
    key = tooth.tooth_number if tooth.tooth_number is not None else tooth.tooth_ref
    session = treatment_sessions.apply_edit(
        session.proposal.case_id,
        key,
        {"translation_x": 0.15},
        reason="numeric_edit",
    )
    after = review_bundle(session)
    assert after["validationCapability"] is not None
    assert after["validationCapability"]["binding"]["setup_version_id"] == session.proposal.version_id
    assert after["validationCapability"]["binding"]["setup_version_id"] != before_setup
    assert after["validationCapability"]["pass_means_clinical_approval"] is False
    assert session.validation is not None


def test_clinical_tool_change_marks_review() -> None:
    session = _session("wp09-tools")
    run = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        configuration=DEFAULT_CONFIG,
        clinical_tools_setup_version_id=session.proposal.version_id,
        current_clinical_tools_setup_version_id=session.proposal.version_id,
    )
    tools = next(
        c for c in run.checks if c.category is ValidationCategory.CLINICAL_TOOL_CONSISTENCY
    )
    assert tools.check_state is ValidationCheckState.REQUIRES_REVIEW


def test_thresholds_are_technical_and_versioned() -> None:
    session = _session("wp09-thr")
    run = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        configuration=DEFAULT_CONFIG,
    )
    assert run.thresholds
    for thr in run.thresholds:
        assert thr.kind == "technical"
        assert thr.version == DEFAULT_CONFIG.engine_version
        assert thr.payload()["clinical_limit"] is False


def test_tooth_and_pair_identity_on_findings() -> None:
    session = _session("wp09-id")
    run = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        configuration=DEFAULT_CONFIG,
    )
    for finding in run.findings:
        if finding.category in (
            ValidationCategory.COLLISION,
            ValidationCategory.PROXIMITY,
            ValidationCategory.CONTACT,
        ):
            assert finding.affected_tooth_refs
            assert finding.spatial_binding is not None
            assert finding.spatial_binding.get("kind") == "tooth_pair"


def test_review_bundle_validation_capability() -> None:
    session = _session("wp09-bundle")
    bundle = review_bundle(session)
    cap = bundle["validationCapability"]
    assert cap["contract_version"] == VALIDATION_CONTRACT_VERSION
    assert cap["summary"]["unavailable_checks"] >= 1
    assert any(c["check_state"] == "not_available" for c in cap["checks"])
    assert cap["clinically_approved"] is False
    assert bundle["validationSummary"]["doctorReview"] == "required"


def test_geometric_engine_still_authoritative() -> None:
    session = _session("wp09-auth")
    report = GeometricValidationEngine().validate(session.staging, DEFAULT_CONFIG)
    assert report.report_id
    run = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=report,
        configuration=DEFAULT_CONFIG,
        occlusion_capability_state="unavailable",
    )
    assert run.binding.geometric_report_id == report.report_id
    assert "GeometricValidationEngine remains the sole geometric authority." in run.limitations


def test_real_case_unavailable_checks_and_no_fdi_fabrication() -> None:
    case_id = "wp09-real"
    _persist_dual_arch(case_id)
    build_and_store_dental_intelligence(case_id)
    session = treatment_sessions.create_engineering_fixture(case_id)
    bundle = review_bundle(session)
    cap = bundle["validationCapability"]
    assert cap["summary"]["unavailable_checks"] >= 1
    checks_by_cat = {c["category"]: c for c in cap["checks"]}
    assert checks_by_cat["occlusion_capability"]["check_state"] == "not_available"
    assert checks_by_cat["root_anatomy"]["check_state"] == "not_available"
    assert checks_by_cat["clinical_axes"]["check_state"] == "not_available"
    assert checks_by_cat["landmarks"]["check_state"] == "not_available"
    for finding in cap["findings"]:
        assert finding.get("clinical_diagnosis") is None


def test_persistence_reopen_validation() -> None:
    session = _session("wp09-persist")
    case_id = session.proposal.case_id
    before = review_bundle(session)
    report_id = session.validation.report_id
    treatment_sessions._sessions.clear()
    reopened = treatment_sessions.get(case_id)
    after = review_bundle(reopened)
    assert after["validationCapability"]["contract_version"] == VALIDATION_CONTRACT_VERSION
    assert reopened.validation.report_id == report_id
    assert before["validationCapability"]["binding"]["geometric_report_id"] == (
        after["validationCapability"]["binding"]["geometric_report_id"]
    )


def test_no_fixture_substitution_claim() -> None:
    session = _session("wp09-fix")
    bundle = review_bundle(session)
    # Engineering fixture is explicit fixture provenance — not silent real substitution
    assert bundle["fixture"] is True or session.proposal.fixture is True
    assert bundle["validationCapability"]["fixture"] in (True, False)


def test_performance_measurements() -> None:
    session = _session("wp09-perf")
    started = time.perf_counter()
    run = build_validation_run(
        case_id=session.proposal.case_id,
        proposal=session.proposal,
        staging=session.staging,
        validation=session.validation,
        configuration=DEFAULT_CONFIG,
        occlusion_capability_state="unavailable",
        root_geometry_state="not_available",
        clinical_axes_state="not_available",
        landmark_state="not_available",
    )
    wall_ms = (time.perf_counter() - started) * 1000
    assert run.timings_ms.get("validation_2_ms") is not None
    print(
        json.dumps(
            {
                "validation_2_ms": run.timings_ms,
                "wall_ms": wall_ms,
                "check_count": run.summary.check_count,
                "finding_count": run.summary.finding_count,
                "unavailable_checks": run.summary.unavailable_checks,
            }
        )
    )
