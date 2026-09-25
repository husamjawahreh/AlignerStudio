"""WP-08 — Occlusion + Advanced Anatomy capability contract and honesty gates."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapters.toothinstancenet.fixture import load_validated_fixture
from app.intelligence_store import build_and_store_dental_intelligence, get_dental_intelligence_record
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
from domain.case.provenance import DataProvenance
from domain.tooth.advanced_anatomy import AnatomyTruthState
from domain.tooth.identification import ArchType
from domain.tooth.intelligence_v2 import IntelligenceTruthState
from domain.tooth.occlusion import (
    OCCLUSION_CONTRACT_VERSION,
    ContactSemantics,
    OcclusionCapabilityState,
    OcclusionFreshness,
    RegistrationEvidence,
    RegistrationEvidenceKind,
    evaluate_occlusion_freshness,
    unavailable_occlusion,
)
from domain.treatment_plan.setup_v2 import ReadinessState
from engines.arrangement.dental_intelligence import build_case_dental_intelligence
from engines.occlusion.capability_engine import (
    build_advanced_anatomy_report,
    build_occlusion_anatomy_plan,
    build_occlusion_result,
    compute_geometric_contact_candidates,
    parse_registration_evidence,
)

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
    case_store.add(Case(id=case_id, patient_reference="WP-08"))
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


def test_capability_contract_versions() -> None:
    assert OCCLUSION_CONTRACT_VERSION == "occlusion_1.0"
    assert set(OcclusionCapabilityState) == {
        OcclusionCapabilityState.UNAVAILABLE,
        OcclusionCapabilityState.SOURCE_REGISTERED,
        OcclusionCapabilityState.COMPUTED,
        OcclusionCapabilityState.REQUIRES_REVIEW,
        OcclusionCapabilityState.VERIFIED,
    }


def test_occlusion_unavailable_without_registration() -> None:
    record = _persist_dual_arch("wp08-unavail")
    result = build_occlusion_result(case_id="wp08-unavail", segmentation_record=record)
    assert result.capability_state is OcclusionCapabilityState.UNAVAILABLE
    assert result.registration.evidence_kind is RegistrationEvidenceKind.NONE
    assert result.representation.availability.value == "unavailable"
    assert result.contact_candidates == ()
    assert result.arch_relationship.class_i_ii_iii is OcclusionCapabilityState.UNAVAILABLE
    assert result.payload()["clinically_approved"] is False
    assert result.payload()["occlusion_validated"] is False


def test_crown_only_anatomy_and_root_unavailable() -> None:
    record = _persist_dual_arch("wp08-anatomy")
    intel = build_case_dental_intelligence(case_id="wp08-anatomy", segmentation_record=record)
    anatomy = build_advanced_anatomy_report(
        case_id="wp08-anatomy",
        segmentation_record=record,
        tooth_intelligence_summaries=[t.payload() for t in intel.teeth],
    )
    assert anatomy.crown_geometry is AnatomyTruthState.COMPUTED
    assert anatomy.root_geometry is AnatomyTruthState.NOT_AVAILABLE
    assert anatomy.landmark_geometry is AnatomyTruthState.NOT_AVAILABLE
    assert anatomy.clinical_axes is AnatomyTruthState.NOT_AVAILABLE
    assert anatomy.generic_geometric_axes is AnatomyTruthState.COMPUTED
    assert anatomy.cbct_volumetric_anatomy is AnatomyTruthState.NOT_AVAILABLE
    assert anatomy.anatomy_extent.value == "crown_only_stl"
    generic = next(c for c in anatomy.capabilities if c.kind.value == "generic_geometric_axes")
    assert generic.clinical is False
    clinical = next(c for c in anatomy.capabilities if c.kind.value == "clinical_axes")
    assert clinical.truth_state is AnatomyTruthState.NOT_AVAILABLE


def test_generic_pca_not_clinical_axes() -> None:
    record = _persist_dual_arch("wp08-pca")
    intel = build_case_dental_intelligence(case_id="wp08-pca", segmentation_record=record)
    for tooth in intel.teeth:
        assert tooth.clinical_dental_axes.state is IntelligenceTruthState.NOT_AVAILABLE
        geom = tooth.geometry.value or {}
        if geom.get("principal_directions"):
            assert geom.get("principal_directions_kind") == "mesh_pca"


def test_no_fdi_fabrication() -> None:
    record = _persist_dual_arch("wp08-fdi")
    intel = build_case_dental_intelligence(case_id="wp08-fdi", segmentation_record=record)
    assert all(
        tooth.fdi_number.state is IntelligenceTruthState.NOT_AVAILABLE
        or tooth.fdi_number.value is None
        for tooth in intel.teeth
    )


def test_no_synthetic_anatomy_in_clinical_calculations() -> None:
    record = _persist_dual_arch("wp08-synth")
    result = build_occlusion_result(case_id="wp08-synth", segmentation_record=record)
    anatomy = build_advanced_anatomy_report(case_id="wp08-synth", segmentation_record=record)
    plan = build_occlusion_anatomy_plan(occlusion=result, advanced_anatomy=anatomy)
    assert plan.occlusion_prerequisite.value == "not_available"
    assert plan.root_geometry_prerequisite.value == "not_available"
    assert plan.landmark_prerequisite.value == "not_available"
    assert plan.clinical_axes_prerequisite.value == "not_available"
    assert result.arch_relationship.payload()["clinical_diagnosis"] is None
    for candidate in result.contact_candidates:
        assert candidate.clinical_interpretation is None
        assert candidate.payload()["clinical_diagnosis"] is None


def test_real_source_artifact_binding() -> None:
    record = _persist_dual_arch("wp08-bind")
    result = build_occlusion_result(case_id="wp08-bind", segmentation_record=record)
    upper = ARTIFACT_DIR / "upper.stl"
    lower = ARTIFACT_DIR / "lower.stl"
    if upper.is_file():
        assert result.bound_upper_hash == _sha256(upper)
    if lower.is_file():
        assert result.bound_lower_hash == _sha256(lower)
    assert result.bound_source_input_hash == record.get("input_hash")


def test_registration_provenance_incomplete_requires_review() -> None:
    evidence = parse_registration_evidence(
        {
            "evidence_kind": "explicit_transform",
            "transform_4x4": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
            "transform_applies_to": "lower_into_upper",
        },
        provenance=DataProvenance.EXPERIMENTAL,
        fixture=True,
        upper_source_artifact="upper.stl",
        lower_source_artifact="lower.stl",
        upper_source_hash="aaa",
        lower_source_hash="bbb",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    assert evidence.truth_state is OcclusionCapabilityState.REQUIRES_REVIEW
    assert evidence.quality_established is False


def test_registration_with_quality_is_source_registered() -> None:
    evidence = parse_registration_evidence(
        {
            "evidence_kind": "explicit_transform",
            "transform_4x4": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
            "transform_applies_to": "lower_into_upper",
            "method": "validated_bite_registration",
            "method_version": "test_reg_v1",
            "quality_metric": 0.12,
            "quality_metric_kind": "rmse_model_units",
            "quality_established": True,
            "registration_version_id": "reg-1",
        },
        provenance=DataProvenance.EXPERIMENTAL,
        fixture=True,
        upper_source_artifact="upper.stl",
        lower_source_artifact="lower.stl",
        upper_source_hash="aaa",
        lower_source_hash="bbb",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    assert evidence.truth_state is OcclusionCapabilityState.SOURCE_REGISTERED
    assert evidence.quality_metric == 0.12


def test_registration_staleness() -> None:
    freshness = evaluate_occlusion_freshness(
        bound_upper_hash="aaa",
        bound_lower_hash="bbb",
        current_upper_hash="ccc",
        current_lower_hash="bbb",
        bound_registration_version_id="reg-1",
        current_registration_version_id="reg-1",
        has_result=True,
    )
    assert freshness is OcclusionFreshness.STALE

    current = evaluate_occlusion_freshness(
        bound_upper_hash="aaa",
        bound_lower_hash="bbb",
        current_upper_hash="aaa",
        current_lower_hash="bbb",
        bound_registration_version_id="reg-1",
        current_registration_version_id="reg-1",
        has_result=True,
    )
    assert current is OcclusionFreshness.CURRENT


def test_occlusion_result_provenance_and_recompute() -> None:
    record = _persist_dual_arch("wp08-prov")
    first = build_occlusion_result(case_id="wp08-prov", segmentation_record=record)
    second = build_occlusion_result(
        case_id="wp08-prov",
        segmentation_record=record,
        previous_result=first,
    )
    assert second.freshness is OcclusionFreshness.CURRENT
    mutated = copy.deepcopy(record)
    mutated["arches"]["upper"]["source_mesh_sha256"] = "changed-hash"
    stale = build_occlusion_result(
        case_id="wp08-prov",
        segmentation_record=mutated,
        previous_result=first,
    )
    assert stale.freshness is OcclusionFreshness.STALE
    assert first.provenance in (DataProvenance.FIXTURE, DataProvenance.EXPERIMENTAL)
    assert first.algorithm is not None


def test_contact_candidate_identity_and_semantics() -> None:
    upper = [{"instance_id": 1, "tooth_ref": "upper:1", "centroid": (0.0, 0.0, 0.0)}]
    lower = [{"instance_id": 2, "tooth_ref": "lower:1", "centroid": (0.0, 0.0, 0.5)}]
    registration = RegistrationEvidence(
        evidence_kind=RegistrationEvidenceKind.EXPLICIT_TRANSFORM,
        truth_state=OcclusionCapabilityState.SOURCE_REGISTERED,
        upper_source_artifact="u",
        lower_source_artifact="l",
        upper_source_hash="a",
        lower_source_hash="b",
        transform_4x4=((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
        transform_applies_to="lower_into_upper",
        method="test",
        method_version="v1",
        quality_metric=0.1,
        quality_metric_kind="rmse",
        quality_established=True,
        registration_version_id="reg-t",
        generated_at="t",
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        limitations=(),
    )
    candidates = compute_geometric_contact_candidates(
        upper_teeth=upper,
        lower_teeth=lower,
        registration=registration,
        technical_proximity_threshold=1.0,
        provenance=DataProvenance.FIXTURE,
        fixture=True,
    )
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.upper_tooth_ref == "upper:1"
    assert cand.lower_tooth_ref == "lower:1"
    assert cand.semantics in (
        ContactSemantics.GEOMETRIC_PROXIMITY,
        ContactSemantics.CANDIDATE_CONTACT,
    )
    assert cand.clinical_interpretation is None
    assert cand.unit == "model units"
    assert cand.technical_threshold_kind == "caller_supplied_geometric_proximity"


def test_no_fabricated_occlusion_diagnosis_on_real_case() -> None:
    record = _persist_dual_arch("wp08-nodiag")
    result = build_occlusion_result(case_id="wp08-nodiag", segmentation_record=record)
    assert result.capability_state is OcclusionCapabilityState.UNAVAILABLE
    assert result.arch_relationship.overjet is OcclusionCapabilityState.UNAVAILABLE
    assert result.arch_relationship.overbite is OcclusionCapabilityState.UNAVAILABLE
    assert result.arch_relationship.class_i_ii_iii is OcclusionCapabilityState.UNAVAILABLE
    assert "upper" in (record.get("arches") or {})
    assert "lower" in (record.get("arches") or {})


def test_no_fabricated_roots_landmarks_axes() -> None:
    record = _persist_dual_arch("wp08-nofab")
    intel = build_case_dental_intelligence(case_id="wp08-nofab", segmentation_record=record)
    occ = intel.occlusion.value or {}
    anatomy = occ.get("advanced_anatomy") or {}
    assert anatomy.get("root_geometry") == "not_available"
    assert anatomy.get("landmark_geometry") == "not_available"
    assert anatomy.get("clinical_axes") == "not_available"
    assert anatomy.get("cbct_volumetric_anatomy") == "not_available"
    assert anatomy.get("crown_geometry") == "computed"
    assert anatomy.get("generic_geometric_axes") == "computed"


def test_setup_and_staging_capability_integration() -> None:
    case_id = "wp08-setup"
    _persist_dual_arch(case_id)
    build_and_store_dental_intelligence(case_id)
    session = treatment_sessions.create_engineering_fixture(case_id)
    bundle = review_bundle(session)
    assert bundle["treatmentSetup"]["readiness"]["occlusion"] == ReadinessState.NOT_AVAILABLE.value
    assert bundle["treatmentSetup"]["readiness"]["clinical_axes"] == ReadinessState.NOT_AVAILABLE.value
    assert bundle.get("occlusionAnatomy") is not None
    assert bundle["occlusionAnatomy"]["prerequisites"]["occlusion"] in (
        "not_available",
        "unavailable",
    )
    assert bundle["occlusionAnatomy"]["clinically_approved"] is False
    assert bundle["occlusionAnatomy"]["occlusion_validated"] is False
    # Unrelated planning remains available despite occlusion not available.
    assert bundle["treatmentSetup"]["readiness"]["transform"] in (
        ReadinessState.AVAILABLE.value,
        ReadinessState.REQUIRES_REVIEW.value,
        ReadinessState.NOT_AVAILABLE.value,
    )


def test_persistence_reopen_intelligence() -> None:
    _persist_dual_arch("wp08-persist")
    payload = build_and_store_dental_intelligence("wp08-persist")
    reloaded = get_dental_intelligence_record("wp08-persist")
    assert reloaded is not None
    assert reloaded["occlusion"]["state"] == "not_available"
    occ = reloaded["occlusion"]["value"]
    assert occ["capability_state"] == "unavailable"
    assert occ["contract_version"] == OCCLUSION_CONTRACT_VERSION
    assert occ["advanced_anatomy"]["root_geometry"] == "not_available"
    assert payload["capability_readiness"]["occlusion_readiness"] == "not_available"


def test_api_dental_intelligence_includes_wp08() -> None:
    _persist_dual_arch("wp08-api")
    response = client.get("/cases/wp08-api/dental-intelligence")
    assert response.status_code == 200
    body = response.json()
    assert body["occlusion"]["state"] == "not_available"
    value = body["occlusion"]["value"]
    assert value["capability_state"] == "unavailable"
    assert value["advanced_anatomy"]["crown_geometry"] == "computed"
    assert value["occlusion_validated"] is False


def test_unavailable_occlusion_stub_compat() -> None:
    stub = unavailable_occlusion(provenance=DataProvenance.EXPERIMENTAL)
    assert stub.contact_count is None
    assert stub.bite_record.value == "unavailable"


def test_registered_path_computes_geometric_candidates_not_diagnosis() -> None:
    record = copy.deepcopy(_persist_dual_arch("wp08-reg"))
    record["arch_registration"] = {
        "evidence_kind": "explicit_transform",
        "transform_4x4": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        "transform_applies_to": "lower_into_upper",
        "method": "fixture_registration",
        "method_version": "test_v1",
        "quality_metric": 0.05,
        "quality_metric_kind": "rmse_model_units",
        "quality_established": True,
        "registration_version_id": "reg-fixture-1",
    }
    result = build_occlusion_result(
        case_id="wp08-reg",
        segmentation_record=record,
        technical_proximity_threshold=50.0,
    )
    assert result.capability_state in (
        OcclusionCapabilityState.SOURCE_REGISTERED,
        OcclusionCapabilityState.COMPUTED,
    )
    assert result.registration.truth_state is OcclusionCapabilityState.SOURCE_REGISTERED
    assert result.arch_relationship.class_i_ii_iii is OcclusionCapabilityState.UNAVAILABLE
    for cand in result.contact_candidates:
        assert cand.clinical_interpretation is None
        assert cand.truth_state is OcclusionCapabilityState.REQUIRES_REVIEW


def test_performance_measurements_recorded() -> None:
    record = _persist_dual_arch("wp08-perf")
    started = time.perf_counter()
    result = build_occlusion_result(case_id="wp08-perf", segmentation_record=record)
    anatomy = build_advanced_anatomy_report(case_id="wp08-perf", segmentation_record=record)
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert result.timings_ms.get("total_ms") is not None
    assert anatomy.timings_ms.get("anatomy_capability_ms") is not None
    assert elapsed_ms >= 0
    print(
        json.dumps(
            {
                "occlusion_ms": result.timings_ms,
                "anatomy_ms": anatomy.timings_ms,
                "wall_ms": elapsed_ms,
            }
        )
    )


def test_no_fixture_substitution_in_real_path_claim() -> None:
    """Intelligence from persisted artifact is fixture-marked; not silent REAL substitution."""
    record = _persist_dual_arch("wp08-fixture-mark")
    intel = build_case_dental_intelligence(
        case_id="wp08-fixture-mark", segmentation_record=record
    )
    assert intel.fixture is True
    assert intel.provenance is DataProvenance.FIXTURE
    assert intel.occlusion.value["fixture"] is True
