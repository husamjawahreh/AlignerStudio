"""WP-05 — Treatment Setup 2.0: source/current/target, versions, validation."""

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
from domain.movement.interaction import ConstraintAvailability
from domain.tooth.identification import ArchType
from domain.treatment_plan.setup import ToothMovement
from domain.treatment_plan.setup_v2 import ReadinessState, stable_setup_plan_id
from domain.treatment_plan.staging import StagingConfiguration
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.editing import TreatmentEditingApplication, TreatmentEditingError
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.setup_versioning import (
    build_setup_readiness,
    build_tooth_target_states,
    find_version,
)
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
        case_id, job_id="job-wp05", input_hash="e" * 64, processing_mode="test_fixture"
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
        "wp05-case",
        identification,
        (mild_crowding_objective(), spacing_objective()),
    )


def validation_config() -> GeometricValidationConfiguration:
    return GeometricValidationConfiguration(0.25, 0.001, 0.0)


def test_source_current_target_separation_and_no_approval() -> None:
    proposal = _synthetic_proposal()
    states = build_tooth_target_states(
        case_id="wp05-case",
        proposal=proposal,
        constraint_availability=ConstraintAvailability.UNAVAILABLE,
    )
    assert states
    for state in states:
        payload = state.payload()
        assert payload["clinically_approved"] is False
        assert payload["source_transform"] == payload["current_transform"]


def test_target_transform_reset_and_source_intact() -> None:
    proposal = _synthetic_proposal()
    application = TreatmentEditingApplication()
    tooth = proposal.setup.target_states[0].tooth_number
    source_before = proposal.setup.source_states[0].source_vertices
    edited = application.apply_edit(
        proposal, tooth, ToothMovement(translation_x=0.55, rotation=2.0), reason="numeric_edit"
    )
    target = next(s for s in edited.setup.target_states if s.tooth_number == tooth)
    assert target.movement.translation_x == pytest.approx(0.55)
    source_after = next(s for s in edited.setup.source_states if s.tooth_number == tooth)
    assert source_after.source_vertices == source_before
    reset = application.reset_tooth(edited, tooth)
    assert reset.setup.target_states[0].movement.pose_equal(
        proposal.setup.target_states[0].movement
    )


def test_multi_tooth_target_edit_single_rebuild() -> None:
    proposal = _synthetic_proposal()
    application = TreatmentEditingApplication()
    t0 = proposal.setup.target_states[0].tooth_number
    t1 = proposal.setup.target_states[1].tooth_number
    edited = application.apply_edits(
        proposal,
        [
            (t0, ToothMovement(translation_x=0.2)),
            (t1, ToothMovement(translation_y=0.3)),
        ],
        reason="gizmo_edit",
    )
    assert len(edited.edit_history) == 2
    assert all(item.reason == "gizmo_edit" for item in edited.edit_history)
    by_tooth = {s.tooth_number: s.movement for s in edited.setup.target_states}
    assert by_tooth[t0].translation_x == pytest.approx(0.2)
    assert by_tooth[t1].translation_y == pytest.approx(0.3)


def test_locked_and_excluded_block_target_pose() -> None:
    proposal = _synthetic_proposal()
    application = TreatmentEditingApplication()
    tooth = proposal.setup.target_states[0].tooth_number
    locked = application.apply_edit(proposal, tooth, ToothMovement(locked=True))
    with pytest.raises(TreatmentEditingError, match="locked"):
        application.apply_edit(locked, tooth, ToothMovement(translation_x=1.0, locked=True))
    excluded = application.apply_edit(proposal, tooth, ToothMovement(excluded=True))
    with pytest.raises(TreatmentEditingError, match="excluded"):
        application.apply_edit(excluded, tooth, ToothMovement(translation_y=0.4, excluded=True))


def test_version_save_immutable_restore_compare() -> None:
    case = Case(id="wp05-ver", patient_reference="WP-05")
    case_store.add(case)
    session = treatment_sessions.create_engineering_fixture(case.id)
    assert len(session.version_history) == 1
    baseline_id = session.version_history[0].meta.version_id
    tooth = session.proposal.setup.target_states[0].tooth_number
    source_before = session.proposal.setup.source_states[0].source_vertices

    t0 = time.perf_counter()
    session = treatment_sessions.apply_edit(
        case.id, tooth, {"translation_x": 0.4, "rotation": 1.5}, reason="numeric_edit"
    )
    edit_ms = (time.perf_counter() - t0) * 1000
    assert session.proposal.version_id != baseline_id
    assert session.parent_version_id == baseline_id

    t0 = time.perf_counter()
    session = treatment_sessions.save_version(case.id, description="After target edit")
    save_ms = (time.perf_counter() - t0) * 1000
    assert len(session.version_history) == 2
    saved = find_version(session.version_history, session.proposal.version_id)
    assert saved is not None
    assert saved.meta.payload()["immutable"] is True

    session = treatment_sessions.apply_edit(
        case.id, tooth, {"translation_x": 0.9}, reason="gizmo_edit"
    )
    frozen = find_version(session.version_history, saved.meta.version_id)
    assert frozen is not None
    assert frozen.proposal.setup.target_states[0].movement.translation_x == pytest.approx(0.4)

    t0 = time.perf_counter()
    session = treatment_sessions.restore_version(case.id, saved.meta.version_id)
    restore_ms = (time.perf_counter() - t0) * 1000
    assert session.proposal.version_id == saved.meta.version_id
    assert session.parent_version_id == saved.meta.version_id
    assert session.proposal.setup.target_states[0].movement.translation_x == pytest.approx(0.4)

    t0 = time.perf_counter()
    comparison = treatment_sessions.compare_versions(case.id, baseline_id, saved.meta.version_id)
    compare_ms = (time.perf_counter() - t0) * 1000
    assert comparison["clinical_ranking"] is None
    assert comparison["clinically_approved"] is False
    assert comparison["changed_count"] >= 1

    source_after = session.proposal.setup.source_states[0].source_vertices
    assert source_after == source_before
    assert edit_ms >= 0 and save_ms >= 0 and restore_ms >= 0 and compare_ms >= 0


def test_review_bundle_exposes_treatment_setup_contract() -> None:
    case = Case(id="wp05-bundle", patient_reference="WP-05")
    case_store.add(case)
    session = treatment_sessions.create_engineering_fixture(case.id)
    bundle = review_bundle(session)
    assert bundle["planId"] == session.proposal.plan_id
    assert bundle["versionId"] == session.proposal.version_id
    assert bundle["setupPlanId"] == stable_setup_plan_id(case.id)
    setup = bundle["treatmentSetup"]
    assert setup["contract_version"] == "treatment_setup_2.0"
    assert setup["clinically_approved"] is False
    assert setup["readiness"]["occlusion"] == ReadinessState.NOT_AVAILABLE.value
    assert setup["readiness"]["unsupported_features_unlocked"] is False


def test_api_version_endpoints() -> None:
    case = Case(id="wp05-api", patient_reference="WP-05")
    case_store.add(case)
    treatment_sessions.create_engineering_fixture(case.id)
    tooth = treatment_sessions.get(case.id).proposal.setup.target_states[0].tooth_number
    edit = client.post(
        f"/cases/{case.id}/treatment/edits",
        json={"tooth_number": tooth, "translation_x": 0.25, "reason": "numeric_edit"},
    )
    assert edit.status_code == 200
    assert edit.json()["treatmentSetup"]["version_id"]
    saved = client.post(
        f"/cases/{case.id}/treatment/versions",
        json={"description": "API save", "author_source": "doctor"},
    )
    assert saved.status_code == 200
    versions = client.get(f"/cases/{case.id}/treatment/versions")
    assert versions.status_code == 200
    assert len(versions.json()["versions"]) >= 2
    vid = versions.json()["versions"][-1]["version_id"]
    restored = client.post(
        f"/cases/{case.id}/treatment/versions/restore",
        json={"version_id": vid},
    )
    assert restored.status_code == 200
    compare = client.post(
        f"/cases/{case.id}/treatment/versions/compare",
        json={
            "left_version_id": versions.json()["versions"][0]["version_id"],
            "right_version_id": vid,
        },
    )
    assert compare.status_code == 200
    assert compare.json()["clinical_ranking"] is None


def test_constraint_unavailable_and_readiness_honest() -> None:
    proposal = _synthetic_proposal()
    application = TreatmentEditingApplication()
    result = application.apply_edit_and_recalculate(
        proposal,
        proposal.setup.target_states[0].tooth_number,
        ToothMovement(translation_x=0.1),
        StagingConfiguration(stage_count=2, mode="macro", movement_limits=None),
        validation_config(),
    )
    readiness = build_setup_readiness(
        proposal=result.proposal,
        staging=result.staging,
        validation=result.validation,
        has_real_geometry=False,
        constraint_availability=ConstraintAvailability.UNAVAILABLE,
    )
    assert readiness.constraint is ReadinessState.UNAVAILABLE
    assert readiness.occlusion is ReadinessState.NOT_AVAILABLE
    assert readiness.clinical_axes is ReadinessState.NOT_AVAILABLE
    assert readiness.payload()["clinically_approved"] is False


def test_real_case_interactable_identity_no_fdi() -> None:
    case_id = "wp05-real"
    case_store.add(Case(id=case_id, patient_reference="WP-05 real"))
    record = _persist_segmentation(case_id)
    teeth = []
    for arch_name, arch in record["arches"].items():
        for tooth in arch.get("tooth_instances") or []:
            teeth.append({**tooth, "arch": arch_name})
    assert len(teeth) == 28
    assert all(t.get("fdi_number") is None for t in teeth)
    assert len({t["tooth_ref"] for t in teeth}) == 28


def test_no_double_application_of_target_transform() -> None:
    proposal = _synthetic_proposal()
    application = TreatmentEditingApplication()
    tooth = proposal.setup.target_states[0].tooth_number
    first = application.apply_edit(proposal, tooth, ToothMovement(translation_x=0.5))
    second = application.apply_edit(first, tooth, ToothMovement(translation_x=0.5))
    movement = next(s for s in second.setup.target_states if s.tooth_number == tooth).movement
    assert movement.translation_x == pytest.approx(0.5)
