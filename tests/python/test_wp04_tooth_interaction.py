"""WP-04 — Tooth Interaction Engine: reversible semantic transforms over P4."""

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
from app.treatment_sessions import treatment_sessions
from domain.case.models import Case
from domain.movement.interaction import (
    ConstraintAvailability,
    CoordinateSpace,
    InteractionPhase,
    can_transform,
    normalize_edit_reason,
    resolve_interaction_phase,
)
from domain.tooth.identification import ArchType
from domain.treatment_plan.setup import ToothMovement
from domain.treatment_plan.staging import StagingConfiguration
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.editing import TreatmentEditingApplication, TreatmentEditingError
from engines.planning.interaction_engine import (
    build_interaction_state,
    commit_tooth_transform,
    constraint_availability_for_proposal,
)
from engines.planning.setup_engine import TreatmentPlanningEngine
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
    pytest.skip("Official real-case artifact is not available in this environment")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


_ARCH_PAYLOAD_CACHE: dict[str, dict] = {}


def _arch_payload_from_artifact(arch: ArchType, artifact: Path) -> dict:
    cache_key = f"{artifact}:{arch.value}"
    if cache_key in _ARCH_PAYLOAD_CACHE:
        return copy.deepcopy(_ARCH_PAYLOAD_CACHE[cache_key])
    result = load_validated_fixture(artifact, arch=arch)
    from time import perf_counter

    diagnostic = _diagnostic_from_result(result, perf_counter(), source_kind="validated_real_case")
    payload = diagnostic.payload()
    stl = ARTIFACT_DIR / f"{arch.value}.stl"
    payload["source_mesh_path"] = str(stl if stl.is_file() else artifact)
    payload["source_mesh_sha256"] = _sha256(stl) if stl.is_file() else None
    payload["fixture"] = True
    payload["processing_mode"] = "test_fixture"
    _ARCH_PAYLOAD_CACHE[cache_key] = payload
    return copy.deepcopy(payload)


def _persist_dual_arch_segmentation(case_id: str) -> dict:
    artifact = _require_artifact()
    begin_segmentation_record(
        case_id,
        job_id="job-wp04",
        input_hash="d" * 64,
        processing_mode="test_fixture",
    )
    for arch in (ArchType.UPPER, ArchType.LOWER):
        payload = _arch_payload_from_artifact(arch, artifact)
        store_arch_result(
            case_id,
            arch.value,
            payload,
            model_name=payload.get("model_name") or "toothinstancenet",
            model_version=payload.get("model_version") or "validated-artifact",
            segment_ms=payload.get("segmentation_runtime_ms"),
        )
    return complete_segmentation_record(case_id, status="completed", total_ms=1.0)


def _build_synthetic_proposal():
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    return TreatmentPlanningEngine().generate(
        "wp04-edit-case",
        identification,
        (mild_crowding_objective(), spacing_objective()),
    )


def validation_config() -> GeometricValidationConfiguration:
    return GeometricValidationConfiguration(0.25, 0.001, 0.0)


def test_interaction_phase_priority() -> None:
    assert (
        resolve_interaction_phase(
            locked=True,
            excluded=True,
            selected=True,
            transforming=True,
            hovered=True,
            available=True,
        )
        is InteractionPhase.LOCKED
    )
    assert (
        resolve_interaction_phase(
            locked=False,
            excluded=True,
            selected=True,
            transforming=False,
            hovered=False,
            available=True,
        )
        is InteractionPhase.EXCLUDED
    )
    assert can_transform(locked=True, excluded=False) is False
    assert can_transform(locked=False, excluded=True) is False
    assert can_transform(locked=False, excluded=False) is True


def test_normalize_edit_reason_never_invents_ai() -> None:
    assert normalize_edit_reason("gizmo_edit") == "gizmo_edit"
    assert normalize_edit_reason("numeric_edit") == "numeric_edit"
    assert normalize_edit_reason("system_restore") == "system_restore"
    assert normalize_edit_reason("ai_generated") == "doctor_edit"
    assert normalize_edit_reason(None) == "doctor_edit"


def test_build_interaction_state_honest_constraints_and_no_approval() -> None:
    base = ToothMovement()
    current = ToothMovement(translation_x=0.5, locked=False, excluded=False)
    state = build_interaction_state(
        case_id="c1",
        tooth_key="upper:instance:0",
        tooth_ref="upper:instance:0",
        arch="upper",
        semantic_label=1,
        fdi_number=None,
        base=base,
        current=current,
        coordinate_space=CoordinateSpace.WORLD,
        constraint_availability=ConstraintAvailability.UNAVAILABLE,
        selected=True,
        source_mesh_sha256="a" * 64,
    )
    payload = state.payload()
    assert payload["clinically_approved"] is False
    assert payload["fdi_number"] is None
    assert payload["constraint_availability"] == "unavailable"
    assert payload["tooth_ref"] == "upper:instance:0"
    assert payload["delta_transform"]["translation_x"] == pytest.approx(0.5)
    assert payload["phase"] == "selected"
    assert any(
        "not clinical" in note.lower() or "not clinically" in note.lower()
        for note in payload["notes"]
    )


def test_commit_translate_rotate_6dof_and_provenance() -> None:
    proposal = _build_synthetic_proposal()
    application = TreatmentEditingApplication()
    tooth = proposal.setup.target_states[0].tooth_number
    source_before = proposal.setup.source_states[0].source_vertices
    movement = ToothMovement(
        translation_x=0.4,
        translation_y=-0.2,
        translation_z=0.1,
        rotation=2.0,
        tip=1.0,
        torque=-1.5,
        angulation=0.5,
        intrusion=0.05,
        extrusion=0.0,
    )
    t0 = time.perf_counter()
    result = commit_tooth_transform(
        application,
        proposal,
        tooth,
        movement,
        reason="numeric_edit",
        staging_configuration=StagingConfiguration(stage_count=2, mode="macro"),
        validation_configuration=validation_config(),
    )
    commit_ms = (time.perf_counter() - t0) * 1000
    edited = result.proposal
    assert edited.edit_history[0].reason == "numeric_edit"
    assert edited.version_id != proposal.version_id
    target = next(s for s in edited.setup.target_states if s.tooth_number == tooth)
    assert target.movement.translation_x == pytest.approx(0.4)
    assert target.movement.rotation == pytest.approx(2.0)
    assert target.movement.tip == pytest.approx(1.0)
    assert target.movement.torque == pytest.approx(-1.5)
    source_after = next(s for s in edited.setup.source_states if s.tooth_number == tooth)
    assert source_after.source_vertices == source_before
    assert result.validation is not None
    assert commit_ms >= 0


def test_locked_tooth_cannot_transform_until_unlocked() -> None:
    proposal = _build_synthetic_proposal()
    application = TreatmentEditingApplication()
    tooth = proposal.setup.target_states[0].tooth_number
    locked = application.apply_edit(
        proposal,
        tooth,
        ToothMovement(locked=True),
        timestamp="1",
        reason="doctor_edit",
    )
    with pytest.raises(TreatmentEditingError, match="locked"):
        application.apply_edit(
            locked,
            tooth,
            ToothMovement(translation_x=1.0, locked=True),
            timestamp="2",
        )
    unlocked = application.apply_edit(
        locked,
        tooth,
        ToothMovement(locked=False),
        timestamp="3",
        reason="doctor_edit",
    )
    moved = application.apply_edit(
        unlocked,
        tooth,
        ToothMovement(translation_x=0.3, locked=False),
        timestamp="4",
        reason="gizmo_edit",
    )
    assert moved.edit_history[-1].reason == "gizmo_edit"
    assert moved.setup.target_states[0].movement.translation_x == pytest.approx(0.3)


def test_excluded_tooth_cannot_pose_transform() -> None:
    proposal = _build_synthetic_proposal()
    application = TreatmentEditingApplication()
    tooth = proposal.setup.target_states[0].tooth_number
    excluded = application.apply_edit(
        proposal,
        tooth,
        ToothMovement(excluded=True),
        timestamp="1",
    )
    with pytest.raises(TreatmentEditingError, match="excluded"):
        application.apply_edit(
            excluded,
            tooth,
            ToothMovement(translation_y=0.5, excluded=True),
            timestamp="2",
        )


def test_reset_and_system_restore_provenance() -> None:
    proposal = _build_synthetic_proposal()
    application = TreatmentEditingApplication()
    tooth = proposal.setup.target_states[0].tooth_number
    original = proposal.setup.target_states[0].movement
    edited = application.apply_edit(
        proposal,
        tooth,
        ToothMovement(translation_x=1.2),
        timestamp="1",
        reason="gizmo_edit",
    )
    reset = application.reset_tooth(edited, tooth, timestamp="2")
    assert reset.setup.target_states[0].movement == original
    assert reset.edit_history[-1].reason == "doctor_reset"
    restored = application.apply_edit(
        reset,
        tooth,
        ToothMovement(translation_x=1.2),
        timestamp="3",
        reason="system_restore",
    )
    assert restored.edit_history[-1].reason == "system_restore"


def test_constraint_unavailable_when_limits_absent() -> None:
    proposal = _build_synthetic_proposal()
    application = TreatmentEditingApplication()
    tooth = proposal.setup.target_states[0].tooth_number
    result = commit_tooth_transform(
        application,
        proposal,
        tooth,
        ToothMovement(translation_x=0.1),
        reason="doctor_edit",
        staging_configuration=StagingConfiguration(
            stage_count=2,
            mode="macro",
            movement_limits=None,
        ),
        validation_configuration=validation_config(),
    )
    availability = constraint_availability_for_proposal(result.proposal, result.staging)
    assert availability in {
        ConstraintAvailability.UNAVAILABLE,
        ConstraintAvailability.NOT_CONFIGURED,
        ConstraintAvailability.CONFIGURED,
    }
    # Staging used movement_limits=None — honesty contract must not invent clinical limits.
    assert availability in {
        ConstraintAvailability.UNAVAILABLE,
        ConstraintAvailability.NOT_CONFIGURED,
    }


def test_real_case_interactable_teeth_preserve_identity_and_no_fdi() -> None:
    case_id = "wp04-real"
    case_store.add(Case(id=case_id, patient_reference="WP-04 patient"))
    record = _persist_dual_arch_segmentation(case_id)
    teeth: list[dict] = []
    for arch_name, arch in (record.get("arches") or {}).items():
        for tooth in arch.get("tooth_instances") or []:
            teeth.append({**tooth, "arch": arch_name})
    assert len(teeth) == 28
    refs = [t.get("tooth_ref") for t in teeth]
    assert all(isinstance(ref, str) and ref for ref in refs)
    assert len(set(refs)) == 28
    assert all(t.get("fdi_number") is None for t in teeth)
    assert all(t.get("arch") in ("upper", "lower") for t in teeth)
    for arch_name in ("upper", "lower"):
        arch = record["arches"][arch_name]
        assert arch.get("source_mesh_sha256")
        assert arch.get("fixture") is True


def test_real_case_interaction_state_mapping_from_semantic_refs() -> None:
    case_id = "wp04-map"
    case_store.add(Case(id=case_id, patient_reference="WP-04 map"))
    record = _persist_dual_arch_segmentation(case_id)
    upper = record["arches"]["upper"]["tooth_instances"]
    tooth = upper[0]
    tooth_ref = tooth["tooth_ref"]
    source_sha = record["arches"]["upper"]["source_mesh_sha256"]
    base = ToothMovement()
    current = ToothMovement(translation_x=0.25, rotation=1.0)
    state = build_interaction_state(
        case_id=case_id,
        tooth_key=tooth_ref,
        tooth_ref=tooth_ref,
        arch="upper",
        semantic_label=tooth.get("semantic_label"),
        fdi_number=tooth.get("fdi_number"),
        base=base,
        current=current,
        coordinate_space=CoordinateSpace.WORLD,
        constraint_availability=ConstraintAvailability.UNAVAILABLE,
        selected=True,
        transforming=False,
        source_mesh_sha256=source_sha,
        version_id="v-test",
    )
    payload = state.payload()
    assert payload["tooth_ref"] == tooth_ref
    assert payload["fdi_number"] is None
    assert payload["source_mesh_sha256"] == source_sha
    assert payload["clinically_approved"] is False
    assert payload["arch"] == "upper"


def test_api_apply_edit_accepts_reason_provenance() -> None:
    from app.routers.cases import MovementEditRequest

    req = MovementEditRequest(
        tooth_ref="upper:instance:0",
        translation_x=0.2,
        reason="numeric_edit",
    )
    assert req.reason == "numeric_edit"
    assert normalize_edit_reason(req.reason) == "numeric_edit"
