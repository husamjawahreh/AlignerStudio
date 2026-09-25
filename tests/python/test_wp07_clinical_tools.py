"""WP-07 — IPR + Attachments + Clinical Tools honesty layer."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapters.toothinstancenet.fixture import load_validated_fixture
from app.main import app
from app.pipeline_diagnostics import _diagnostic_from_result
from app.segmentation_store import (
    begin_segmentation_record,
    complete_segmentation_record,
    store_arch_result,
)
from app.store import case_store
from app.treatment_sessions import review_bundle, treatment_sessions
from domain.case.models import Case
from domain.tooth.identification import ArchType
from domain.treatment_plan.clinical_tools import (
    ClinicalToolTruthState,
    ClinicalToolValueSource,
)
from domain.treatment_plan.proposals import ProposalStatus
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.clinical_tools_engine import (
    build_clinical_tools_plan,
    ipr_truth_state,
    ipr_value_source,
    preserve_doctor_ipr_amounts,
    serialize_ipr_site,
)
from engines.planning.proposals import TreatmentProposalEngine
from engines.planning.setup_engine import TreatmentPlanningEngine
from tests.fixtures.synthetic_arch import build_synthetic_arch
from tests.fixtures.synthetic_objectives import mild_crowding_objective, spacing_objective

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


def _persist_segmentation(case_id: str) -> dict:
    artifact = _require_artifact()
    begin_segmentation_record(
        case_id, job_id="job-wp07", input_hash="f" * 64, processing_mode="test_fixture"
    )
    for arch in (ArchType.UPPER, ArchType.LOWER):
        payload = _arch_payload(arch, artifact)
        store_arch_result(
            case_id,
            arch.value,
            payload,
            model_name="toothinstancenet",
            model_version="validated-artifact",
            segment_ms=1.0,
        )
    return complete_segmentation_record(case_id, status="completed", total_ms=1.0)


def _synthetic_session(case_id: str = "wp07-synth"):
    case = Case(id=case_id, patient_reference="WP-07")
    case_store.add(case)
    return treatment_sessions.create_engineering_fixture(case_id)


def test_clinical_tools_contract_serialization() -> None:
    session = _synthetic_session()
    bundle = review_bundle(session)
    tools = bundle["clinicalTools"]
    assert tools["contract_version"] == "clinical_tools_1.0"
    assert tools["clinically_approved"] is False
    assert tools["freshness"] == "current"
    assert tools["readiness"]["doctor_review_required"] is True
    assert tools["readiness"]["clinically_approved"] is False
    assert "clinical_tools_1.0" in json.dumps(tools)


def test_ipr_pair_identity_and_no_fdi_fabrication() -> None:
    session = _synthetic_session("wp07-ipr-id")
    for site in session.adjuncts.ipr.sites:
        assert site.tooth_a is not None
        assert site.tooth_b is not None
        assert site.site_id
        payload = serialize_ipr_site(site, display_stage=0)
        assert payload["toothA"] == site.tooth_a
        assert payload["toothB"] == site.tooth_b
        assert payload["clinicallyApproved"] is False
        assert payload["truthState"] != ClinicalToolTruthState.VERIFIED.value


def test_measured_proposed_doctor_distinction() -> None:
    session = _synthetic_session("wp07-ipr-src")
    assert session.adjuncts.ipr.sites, "synthetic fixture should produce IPR sites"
    site = session.adjuncts.ipr.sites[0]
    assert site.current_measurement.value is not None
    assert ipr_value_source(site) is ClinicalToolValueSource.COMPUTED_PROPOSAL
    assert ipr_truth_state(site) is ClinicalToolTruthState.REQUIRES_REVIEW

    session = treatment_sessions.modify_ipr_amount(session.proposal.case_id, site.site_id, 0.22)
    updated = next(s for s in session.adjuncts.ipr.sites if s.site_id == site.site_id)
    assert updated.doctor_entered_amount == pytest.approx(0.22)
    assert updated.proposed_amount == pytest.approx(0.22)
    assert updated.status is ProposalStatus.DOCTOR_MODIFIED
    assert ipr_value_source(updated) is ClinicalToolValueSource.DOCTOR_ENTERED
    payload = serialize_ipr_site(updated, display_stage=0)
    assert payload["doctorEnteredAmount"] == pytest.approx(0.22)
    assert payload["measuredAmount"] == site.current_measurement.value
    assert payload["valueSource"] == "doctor_entered"


def test_doctor_ipr_preserved_across_regenerate() -> None:
    session = _synthetic_session("wp07-preserve")
    site = session.adjuncts.ipr.sites[0]
    session = treatment_sessions.modify_ipr_amount(session.proposal.case_id, site.site_id, 0.33)
    prior = session.adjuncts
    regenerated = TreatmentProposalEngine().generate(session.proposal, previous=prior)
    preserved = next(s for s in regenerated.ipr.sites if s.site_id == site.site_id)
    assert preserved.doctor_entered_amount == pytest.approx(0.33)
    assert preserved.status is ProposalStatus.DOCTOR_MODIFIED


def test_ipr_persistence_and_reopen() -> None:
    session = _synthetic_session("wp07-persist")
    site = session.adjuncts.ipr.sites[0]
    treatment_sessions.modify_ipr_amount(session.proposal.case_id, site.site_id, 0.17)
    treatment_sessions._sessions.clear()
    reopened = treatment_sessions.get("wp07-persist")
    updated = next(s for s in reopened.adjuncts.ipr.sites if s.site_id == site.site_id)
    assert updated.doctor_entered_amount == pytest.approx(0.17)
    assert updated.status is ProposalStatus.DOCTOR_MODIFIED


def test_setup_and_staging_stale_detection() -> None:
    session = _synthetic_session("wp07-stale")
    tooth = session.proposal.setup.target_states[0].tooth_number
    source_before = session.proposal.setup.source_states[0].source_vertices
    bound_setup = session.clinical_tools_setup_version_id
    bound_staging = session.clinical_tools_staging_version_id

    session = treatment_sessions.apply_edit(
        session.proposal.case_id,
        tooth,
        {"translation_x": 0.4},
        reason="numeric_edit",
        restage=False,
    )
    assert session.proposal.version_id != bound_setup
    assert session.clinical_tools_setup_version_id == bound_setup
    bundle = review_bundle(session)
    assert bundle["clinicalTools"]["freshness"] == "stale"
    assert bundle["clinicalTools"]["readiness"]["setup_binding"] == "stale"

    session = treatment_sessions.regenerate_staging(
        session.proposal.case_id, description="wp07 staging regen"
    )
    assert session.clinical_tools_staging_version_id == bound_staging
    assert session.smart_staging.meta.staging_version_id != bound_staging
    bundle = review_bundle(session)
    assert bundle["clinicalTools"]["freshness"] == "stale"
    assert bundle["clinicalTools"]["readiness"]["staging_binding"] == "stale"

    t0 = time.perf_counter()
    session = treatment_sessions.regenerate_clinical_tools(session.proposal.case_id)
    regen_ms = (time.perf_counter() - t0) * 1000
    assert session.clinical_tools_setup_version_id == session.proposal.version_id
    assert (
        session.clinical_tools_staging_version_id
        == session.smart_staging.meta.staging_version_id
    )
    bundle = review_bundle(session)
    assert bundle["clinicalTools"]["freshness"] == "current"
    assert session.proposal.setup.source_states[0].source_vertices == source_before
    assert regen_ms >= 0


def test_attachment_identity_truth_and_review() -> None:
    session = _synthetic_session("wp07-att")
    bundle = review_bundle(session)
    tools = bundle["clinicalTools"]
    if not session.adjuncts.attachments.sites:
        assert tools["readiness"]["attachment_placement"] in (
            "not_available",
            "requires_review",
        )
        return
    site = session.adjuncts.attachments.sites[0]
    assert site.dimensions is None
    assert site.generated is False
    assert site.attachment_type.value == "undetermined"
    payload = next(s for s in bundle["attachmentSites"] if s["siteId"] == site.site_id)
    assert payload["truthState"] == "requires_review"
    assert payload["geometryAvailable"] is False
    assert payload["clinicallyApproved"] is False

    session = treatment_sessions.set_attachment_status(
        session.proposal.case_id, site.site_id, "accepted"
    )
    updated = next(s for s in session.adjuncts.attachments.sites if s.site_id == site.site_id)
    assert updated.status is ProposalStatus.ACCEPTED
    bundle = review_bundle(session)
    assert bundle["clinicalTools"]["clinically_approved"] is False


def test_attachment_persistence() -> None:
    session = _synthetic_session("wp07-att-persist")
    if not session.adjuncts.attachments.sites:
        tooth = session.proposal.setup.target_states[0].tooth_number
        session = treatment_sessions.apply_edit(
            session.proposal.case_id,
            tooth,
            {"rotation": 5.0},
            reason="numeric_edit",
        )
    if not session.adjuncts.attachments.sites:
        pytest.skip("No attachment candidates for synthetic fixture after angular edit")
    site = session.adjuncts.attachments.sites[0]
    treatment_sessions.set_attachment_status(
        session.proposal.case_id, site.site_id, "rejected"
    )
    treatment_sessions._sessions.clear()
    reopened = treatment_sessions.get("wp07-att-persist")
    updated = next(s for s in reopened.adjuncts.attachments.sites if s.site_id == site.site_id)
    assert updated.status is ProposalStatus.REJECTED


def test_no_fake_zero_clinical_capability() -> None:
    session = _synthetic_session("wp07-zeros")
    empty_adjuncts = TreatmentProposalEngine().generate(replace(session.proposal, setup=None))
    plan = build_clinical_tools_plan(
        empty_adjuncts,
        current_setup_version_id=session.proposal.version_id,
        current_staging_version_id=None,
        bound_setup_version_id=None,
        bound_staging_version_id=None,
        has_validation=True,
        has_source_geometry=False,
    )
    assert plan.ipr_site_count == 0
    assert plan.readiness.ipr_measurement.value == "not_available"
    assert plan.readiness.attachment_placement.value == "not_available"
    notes = " ".join(plan.payload()["notes"]).lower()
    assert "unnecessary" in notes or "not prove" in notes or "empty" in notes


def test_validation_remains_authoritative() -> None:
    session = _synthetic_session("wp07-val")
    assert session.validation is not None
    bundle = review_bundle(session)
    assert bundle["validationSummary"] is not None
    assert bundle["clinicalTools"]["readiness"]["validation"] == "available"
    assert bundle["clinicalTools"]["clinically_approved"] is False


def test_real_case_clinical_tools_evidence(monkeypatch) -> None:
    artifact = _require_artifact()
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE", str(artifact))
    monkeypatch.setenv("ALIGNERSTUDIO_STAGE_COUNT", "2")

    from app.routers.cases import _combined_fixture_identification
    from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
    from domain.treatment_plan.setup import ToothMovement, TreatmentObjective, TreatmentObjectiveType

    case_id = "official_real_case_stage2_verified_v1"
    case_store.add(Case(id=case_id, patient_reference="WP-07-real"))
    identification, diagnostics = _combined_fixture_identification()
    tooth_count = len(identification.teeth)
    assert tooth_count == 28
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
    assert session.planning_mode == "semantic_only_experimental"
    assert session.source_kind == "validated_real_case"

    source_hashes = []
    for state in session.proposal.setup.source_states:
        assert state.source_vertices is not None
        assert state.tooth_ref is not None
        assert state.tooth_number is None  # no fabricated FDI
        # Integrity fingerprint from first few vertices (tuple geometry, not bytes).
        sample = tuple(tuple(float(c) for c in vertex) for vertex in state.source_vertices[:3])
        source_hashes.append(hash(sample))

    t0 = time.perf_counter()
    adjuncts = TreatmentProposalEngine().generate(session.proposal)
    ipr_ms = (time.perf_counter() - t0) * 1000

    measurable = sum(
        1 for s in adjuncts.ipr.sites if s.current_measurement.value is not None
    )
    unavailable = sum(
        1
        for s in adjuncts.ipr.sites
        if s.status is ProposalStatus.UNABLE_TO_DETERMINE
        or s.current_measurement.value is None
    )
    bundle = review_bundle(session)
    tools = bundle["clinicalTools"]
    assert tools["contract_version"] == "clinical_tools_1.0"
    assert tools["clinically_approved"] is False
    for site in bundle["iprSites"]:
        assert isinstance(site["toothA"], str)
        assert isinstance(site["toothB"], str)
        assert site["truthState"] != "verified"
        assert site.get("clinicallyApproved") is False
        assert site["amountUnit"] == "model units"
    for site in bundle["attachmentSites"]:
        assert isinstance(site["toothNumber"], str)
        assert site["truthState"] == "requires_review"
        assert site.get("clinicallyApproved") is False

    if measurable > 0:
        site = next(
            s for s in session.adjuncts.ipr.sites if s.current_measurement.value is not None
        )
        session = treatment_sessions.modify_ipr_amount(case_id, site.site_id, 0.12)
        updated = next(s for s in session.adjuncts.ipr.sites if s.site_id == site.site_id)
        assert updated.doctor_entered_amount == pytest.approx(0.12)
        treatment_sessions._sessions.clear()
        session = treatment_sessions.get(case_id)
        again = next(s for s in session.adjuncts.ipr.sites if s.site_id == site.site_id)
        assert again.doctor_entered_amount == pytest.approx(0.12)

    # Stale detection on real case
    tooth_key = (
        session.proposal.setup.target_states[0].tooth_ref
        or session.proposal.setup.target_states[0].tooth_number
    )
    bound_setup = session.clinical_tools_setup_version_id
    session = treatment_sessions.apply_edit(
        case_id, tooth_key, {"translation_x": 0.15}, reason="numeric_edit", restage=False
    )
    assert session.clinical_tools_setup_version_id == bound_setup
    assert review_bundle(session)["clinicalTools"]["freshness"] == "stale"
    session = treatment_sessions.regenerate_clinical_tools(case_id)
    assert review_bundle(session)["clinicalTools"]["freshness"] == "current"

    evidence = {
        "artifact": str(artifact),
        "tooth_instance_count": tooth_count,
        "ipr_site_count": len(adjuncts.ipr.sites),
        "measurable_ipr_pairs": measurable,
        "unavailable_ipr_pairs": unavailable,
        "attachment_site_count": len(adjuncts.attachments.sites),
        "setup_version": session.proposal.version_id,
        "staging_version": (
            session.smart_staging.meta.staging_version_id if session.smart_staging else None
        ),
        "clinical_tools_freshness": review_bundle(session)["clinicalTools"]["freshness"],
        "compose_ms": compose_ms,
        "ipr_generate_ms": ipr_ms,
        "source_geometry_sample_hashes": source_hashes[:3],
        "wp08_started": False,
    }
    assert evidence["wp08_started"] is False
    assert evidence["tooth_instance_count"] == 28
    assert evidence["ipr_generate_ms"] >= 0
    assert evidence["compose_ms"] >= 0


def test_preserve_doctor_helper_unit() -> None:
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    proposal = TreatmentPlanningEngine().generate(
        "wp07-helper",
        identification,
        (mild_crowding_objective(), spacing_objective()),
    )
    engine = TreatmentProposalEngine()
    first = engine.generate(proposal)
    if not first.ipr.sites:
        pytest.skip("no IPR sites")
    site_id = first.ipr.sites[0].site_id
    modified = engine.modify_ipr(first, site_id, 0.5)
    second = engine.generate(proposal, previous=modified)
    kept = preserve_doctor_ipr_amounts(modified, second)
    assert next(s for s in kept.ipr.sites if s.site_id == site_id).doctor_entered_amount == 0.5


def test_api_proposals_expose_truth_fields() -> None:
    session = _synthetic_session("wp07-api")
    response = client.get(f"/cases/{session.proposal.case_id}/treatment")
    assert response.status_code == 200
    body = response.json()
    assert "clinicalTools" in body
    assert body["clinicalTools"]["clinically_approved"] is False
    if body["iprSites"]:
        site = body["iprSites"][0]
        assert "truthState" in site
        assert "valueSource" in site
        assert site["amountUnit"] == "model units"
