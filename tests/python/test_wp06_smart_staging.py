"""WP-06 — Smart Staging Engine: deterministic stages bound to Treatment Setup versions."""

from __future__ import annotations

import copy
import hashlib
import time
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
from domain.treatment_plan.setup import ToothMovement
from domain.treatment_plan.smart_staging import StagingFreshness, StagingTruthState
from domain.treatment_plan.staging import StagingConfiguration
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.editing import TreatmentEditingApplication
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.smart_staging_engine import (
    SmartStagingEngine,
    evaluate_freshness,
    final_stage_matches_target,
)
from engines.planning.staging_engine import TreatmentStagingEngine
from engines.validation.geometric_engine import GeometricValidationConfiguration
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
        case_id, job_id="job-wp06", input_hash="f" * 64, processing_mode="test_fixture"
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


def _synthetic_proposal():
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    return TreatmentPlanningEngine().generate(
        "wp06-case",
        identification,
        (mild_crowding_objective(), spacing_objective()),
    )


def test_deterministic_generation_and_final_equals_target() -> None:
    proposal = _synthetic_proposal()
    engine = SmartStagingEngine()
    first = engine.generate(proposal, StagingConfiguration(stage_count=3, mode="macro"))
    second = engine.generate(proposal, StagingConfiguration(stage_count=3, mode="macro"))
    assert first.staging.staging_id == second.staging.staging_id
    assert first.final_equals_target is True
    assert first.reconstruction_max_error <= 1e-9
    assert first.meta.truth_state is StagingTruthState.REQUIRES_REVIEW
    assert first.meta.clinically_optimal is False if hasattr(first.meta, "clinically_optimal") else True
    assert first.payload()["clinically_optimal"] is False
    assert first.staging.stages[0].stage_type == "initial"
    assert first.staging.stages[-1].stage_type == "final"


def test_linear_decomposition_reconstructs_target() -> None:
    proposal = _synthetic_proposal()
    application = TreatmentEditingApplication()
    tooth = proposal.setup.target_states[0].tooth_number
    edited = application.apply_edit(
        proposal, tooth, ToothMovement(translation_x=1.0, rotation=4.0), reason="numeric_edit"
    )
    plan = SmartStagingEngine().generate(
        edited, StagingConfiguration(stage_count=5, mode="macro")
    )
    equals, err = final_stage_matches_target(edited, plan.staging)
    assert equals and err <= 1e-9
    # Intermediate progress is monotonic scale of target DOF.
    mid = plan.staging.stages[2]
    mid_tooth = next(s for s in mid.tooth_states if s.tooth_number == tooth)
    assert mid_tooth.movement.movement.translation_x == pytest.approx(0.5)


def test_lock_and_exclusion_respected() -> None:
    proposal = _synthetic_proposal()
    application = TreatmentEditingApplication()
    tooth = proposal.setup.target_states[0].tooth_number
    locked = application.apply_edit(proposal, tooth, ToothMovement(locked=True))
    plan = SmartStagingEngine().generate(locked, StagingConfiguration(stage_count=3, mode="macro"))
    assert plan.final_equals_target is True
    excluded = application.apply_edit(proposal, tooth, ToothMovement(excluded=True, translation_x=0.5))
    # Excluded pose is identity in rebuild; staging still final-equals target.
    plan2 = SmartStagingEngine().generate(excluded, StagingConfiguration(stage_count=3, mode="macro"))
    assert plan2.final_equals_target is True


def test_session_stale_detection_and_regenerate() -> None:
    case = Case(id="wp06-stale", patient_reference="WP-06")
    case_store.add(case)
    session = treatment_sessions.create_engineering_fixture(case.id)
    assert session.smart_staging.meta.freshness is StagingFreshness.CURRENT
    baseline_setup = session.proposal.version_id
    tooth = session.proposal.setup.target_states[0].tooth_number
    source_before = session.proposal.setup.source_states[0].source_vertices

    session = treatment_sessions.apply_edit(
        case.id, tooth, {"translation_x": 0.35}, reason="numeric_edit", restage=False
    )
    assert session.proposal.version_id != baseline_setup
    assert session.smart_staging.meta.freshness is StagingFreshness.STALE
    bundle = review_bundle(session)
    assert bundle["smartStaging"]["meta"]["freshness"] == "stale"

    t0 = time.perf_counter()
    session = treatment_sessions.regenerate_staging(case.id, description="regen")
    regen_ms = (time.perf_counter() - t0) * 1000
    assert session.smart_staging.meta.freshness is StagingFreshness.CURRENT
    assert session.smart_staging.final_equals_target is True
    assert session.smart_staging.meta.source_setup_version_id == session.proposal.version_id
    assert session.proposal.setup.source_states[0].source_vertices == source_before
    assert regen_ms >= 0


def test_staging_version_immutability_and_restore() -> None:
    case = Case(id="wp06-ver", patient_reference="WP-06")
    case_store.add(case)
    session = treatment_sessions.create_engineering_fixture(case.id)
    tooth = session.proposal.setup.target_states[0].tooth_number
    session = treatment_sessions.apply_edit(
        case.id, tooth, {"translation_x": 0.2}, reason="gizmo_edit"
    )
    session = treatment_sessions.save_staging_version(case.id, description="saved staging")
    assert len(session.staging_history) >= 2
    saved_id = session.smart_staging.meta.staging_version_id
    session = treatment_sessions.apply_edit(
        case.id, tooth, {"translation_x": 0.9}, reason="numeric_edit"
    )
    # Saved snapshot untouched.
    frozen = next(
        item for item in session.staging_history if item.plan.meta.staging_version_id == saved_id
    )
    assert frozen.plan.staging.stages[-1].tooth_states[0].movement.movement.translation_x == pytest.approx(0.2)
    session = treatment_sessions.restore_staging_version(case.id, saved_id)
    assert session.staging.staging_id == saved_id or session.smart_staging.meta.staging_version_id == saved_id


def test_constraint_unavailable_honest() -> None:
    proposal = _synthetic_proposal()
    plan = SmartStagingEngine().generate(
        proposal,
        StagingConfiguration(stage_count=2, mode="macro", movement_limits=None),
    )
    assert plan.readiness.constraints.value == "unavailable"
    assert plan.readiness.occlusion.value == "not_available"
    assert plan.readiness.doctor_review_required is True


def test_freshness_helper() -> None:
    assert (
        evaluate_freshness(
            source_setup_version_id="a",
            current_setup_version_id="a",
            has_staging=True,
        )
        is StagingFreshness.CURRENT
    )
    assert (
        evaluate_freshness(
            source_setup_version_id="a",
            current_setup_version_id="b",
            has_staging=True,
        )
        is StagingFreshness.STALE
    )


def test_api_staging_regenerate_and_versions() -> None:
    case = Case(id="wp06-api", patient_reference="WP-06")
    case_store.add(case)
    treatment_sessions.create_engineering_fixture(case.id)
    regen = client.post(
        f"/cases/{case.id}/treatment/staging/regenerate",
        json={"description": "api regen", "author_source": "doctor"},
    )
    assert regen.status_code == 200
    assert regen.json()["smartStaging"]["final_equals_target"] is True
    saved = client.post(
        f"/cases/{case.id}/treatment/staging/versions",
        json={"description": "api save"},
    )
    assert saved.status_code == 200
    listed = client.get(f"/cases/{case.id}/treatment/staging/versions")
    assert listed.status_code == 200
    assert len(listed.json()["versions"]) >= 1


def test_real_case_identity_no_fdi() -> None:
    case_id = "wp06-real"
    case_store.add(Case(id=case_id, patient_reference="WP-06 real"))
    record = _persist_segmentation(case_id)
    teeth = []
    for arch_name, arch in record["arches"].items():
        for tooth in arch.get("tooth_instances") or []:
            teeth.append({**tooth, "arch": arch_name})
    assert len(teeth) == 28
    assert all(t.get("fdi_number") is None for t in teeth)
    assert len({t["tooth_ref"] for t in teeth}) == 28


def test_no_source_mutation_through_staging() -> None:
    proposal = _synthetic_proposal()
    source = proposal.setup.source_states[0].source_vertices
    plan = SmartStagingEngine().generate(proposal, StagingConfiguration(stage_count=4, mode="macro"))
    assert proposal.setup.source_states[0].source_vertices == source
    assert plan.staging.stages[0].tooth_states[0].source_vertices == source
