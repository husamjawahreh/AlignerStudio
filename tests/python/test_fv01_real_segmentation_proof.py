"""FV-01 real segmentation proof: probe, contract, binding, and fixture firewall."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from app.pipeline_diagnostics import PipelineState, process_uploaded_case
from app.processing_modes import ProcessingModeError, require_real_case_mode
from app.segmentation_store import (
    begin_segmentation_record,
    complete_segmentation_record,
    get_segmentation_record,
    store_arch_result,
)
from app.store import InMemoryCaseStore

from adapters.toothinstancenet.contract import ToothInstanceNetRawOutput
from domain.case.models import Case, CaseStatus
from domain.tooth.identification import ArchType
from domain.tooth.segmentation_proof import (
    SegmentationProofError,
    assert_segmentation_bound,
    build_segmentation_contract,
)
from engines.segmentation.fv01_probe import _primary_state, run_fv01_probe
from engines.segmentation.toothinstancenet import ToothInstanceNetEngine


def test_probe_state_machine_distinguishes_blockers() -> None:
    gpu_down = {"nvidia_driver_visible": False}
    gpu_up = {"nvidia_driver_visible": True}
    torch_down = {"available": False, "cuda_available": False, "cuda_tensor_executed": False}
    torch_up = {"available": True, "cuda_available": True, "cuda_tensor_executed": True}
    missing = {"present": False, "matches_pinned_digest": None}
    present = {"present": True, "matches_pinned_digest": True}
    assert (
        _primary_state(
            gpu=gpu_down,
            torch_facts=torch_down,
            checkpoint=present,
            source_configured=True,
            pointops_present=True,
            backend="toothinstancenet",
            contract_state="MODEL_CONTRACT_UNKNOWN",
            inference_executed=False,
            inference_failed=False,
        )
        == "GPU_UNAVAILABLE"
    )
    assert (
        _primary_state(
            gpu=gpu_up,
            torch_facts=torch_up,
            checkpoint=missing,
            source_configured=True,
            pointops_present=True,
            backend="toothinstancenet",
            contract_state="MODEL_CONTRACT_UNKNOWN",
            inference_executed=False,
            inference_failed=False,
        )
        == "MODEL_MISSING"
    )
    assert (
        _primary_state(
            gpu=gpu_up,
            torch_facts=torch_up,
            checkpoint=present,
            source_configured=False,
            pointops_present=False,
            backend="toothinstancenet",
            contract_state="MODEL_CONTRACT_UNKNOWN",
            inference_executed=False,
            inference_failed=False,
        )
        == "DEPENDENCY_MISSING"
    )
    assert (
        _primary_state(
            gpu=gpu_up,
            torch_facts=torch_up,
            checkpoint=present,
            source_configured=True,
            pointops_present=True,
            backend="onnx",
            contract_state="MODEL_CONTRACT_KNOWN",
            inference_executed=False,
            inference_failed=False,
        )
        == "BACKEND_UNAVAILABLE"
    )
    assert (
        _primary_state(
            gpu=gpu_up,
            torch_facts=torch_up,
            checkpoint=present,
            source_configured=True,
            pointops_present=True,
            backend="toothinstancenet",
            contract_state="MODEL_CONTRACT_UNKNOWN",
            inference_executed=False,
            inference_failed=False,
        )
        == "MODEL_CONTRACT_UNKNOWN"
    )
    assert (
        _primary_state(
            gpu=gpu_up,
            torch_facts=torch_up,
            checkpoint=present,
            source_configured=True,
            pointops_present=True,
            backend="toothinstancenet",
            contract_state="MODEL_CONTRACT_KNOWN",
            inference_executed=True,
            inference_failed=False,
        )
        == "INFERENCE_READY"
    )
    assert (
        _primary_state(
            gpu=gpu_up,
            torch_facts=torch_up,
            checkpoint=present,
            source_configured=True,
            pointops_present=True,
            backend="toothinstancenet",
            contract_state="MODEL_CONTRACT_KNOWN",
            inference_executed=True,
            inference_failed=True,
        )
        == "INFERENCE_FAILED"
    )


def test_host_probe_does_not_claim_inference(tmp_path: Path) -> None:
    report = run_fv01_probe(hash_checkpoint=False, checkpoint_path=tmp_path / "missing.ckpt")
    assert report["inference_can_execute"] is False
    assert report["fixture_selected"] is False
    assert report["clinical_accuracy_claim"] is False
    assert report["primary_state"] == "GPU_UNAVAILABLE"
    assert "DEPENDENCY_MISSING" in report["applicable_states"]
    assert report["contract"]["state"] == "MODEL_CONTRACT_UNKNOWN"
    assert report["contract"]["tensor_contract_rederived"] is False
    assert report["expected_output"]["fdi_produced_by_model"] is False
    assert report["performance"]["inference_ms"] is None
    assert report["performance"]["probe_ms"] >= 0


def test_real_case_refuses_fixture_backend(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
    with pytest.raises(ProcessingModeError, match="refuses toothinstancenet_fixture"):
        require_real_case_mode()


def test_real_case_with_fixture_available_does_not_load_it(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(tmp_path))
    uploaded = tmp_path / "patient.stl"
    uploaded.write_bytes(b"solid patient\nendsolid patient\n")
    diagnostic = process_uploaded_case(str(uploaded), ArchType.UPPER, input_hash="a" * 64)
    assert diagnostic.fixture is False
    assert diagnostic.processing_mode == "real_case"
    assert diagnostic.state in {
        PipelineState.MODEL_UNAVAILABLE,
        PipelineState.BLOCKED_BY_ENVIRONMENT,
        PipelineState.SEGMENTATION_FAILED,
    }
    assert diagnostic.tooth_instance_count == 0
    contract = diagnostic.segmentation_contract
    assert contract is not None
    assert contract["fixture"] is False
    assert contract["clinical_accuracy_claim"] is False
    assert contract["output_class"] == "ENGINEERING_OUTPUT"
    assert contract["fdi_authoritative"] is False
    assert contract["source_mesh_hash"] == hashlib.sha256(uploaded.read_bytes()).hexdigest()
    assert contract["tooth_instances"] == []


def test_persisted_contract_reopens_and_rejects_other_mesh(tmp_path: Path) -> None:
    store = InMemoryCaseStore(tmp_path / "cases.json")
    now = datetime.now(UTC)
    case = Case(id="case-fv01", patient_reference="fv01", status=CaseStatus.CREATED, created_at=now)
    store.add(case)
    mesh_hash = "b" * 64
    other_hash = "c" * 64
    case_hash = "d" * 64
    contract = build_segmentation_contract(
        case_id="case-fv01",
        job_id="job-fv01",
        case_input_hash=case_hash,
        source_mesh_hash=mesh_hash,
        arch="upper",
        model_name="toothinstancenet",
        model_version="unrun",
        checkpoint_sha256=None,
        backend="toothinstancenet",
        algorithm_version="toothinstancenet-segmentation",
        inference_status="GPU_UNAVAILABLE",
        instances=[],
        truth_state="blocked_by_environment",
        limitations=("clinical_accuracy_claim=false.",),
        provenance="experimental",
        created_at=now.isoformat(),
        fixture=False,
    )
    import app.segmentation_store as segmentation_store

    original = segmentation_store.case_store
    segmentation_store.case_store = store
    try:
        begin_segmentation_record(
            "case-fv01",
            job_id="job-fv01",
            input_hash=case_hash,
            processing_mode="real_case",
        )
        store_arch_result(
            "case-fv01",
            "upper",
            {
                "fixture": False,
                "source_mesh_sha256": mesh_hash,
                "segmentation_contract": contract,
                "state": "blocked_by_environment",
            },
        )
        complete_segmentation_record("case-fv01", status="blocked_by_environment")
        reopened = InMemoryCaseStore(store.path)
        saved = reopened.get("case-fv01")
        assert saved is not None
        record = saved.segmentation_results
        assert record["input_hash"] == case_hash
        assert record["arches"]["upper"]["segmentation_contract"]["source_mesh_hash"] == mesh_hash
        saved_contract = record["arches"]["upper"]["segmentation_contract"]
        assert saved_contract["clinical_accuracy_claim"] is False
        assert_segmentation_bound(
            record["arches"]["upper"]["segmentation_contract"],
            uploaded_mesh_sha256=mesh_hash,
            case_input_hash=case_hash,
        )
        with pytest.raises(SegmentationProofError, match="source hash"):
            assert_segmentation_bound(
                record["arches"]["upper"]["segmentation_contract"],
                uploaded_mesh_sha256=other_hash,
            )
        with pytest.raises(ValueError, match="Fixture segmentation"):
            store_arch_result(
                "case-fv01",
                "lower",
                {"fixture": True, "source_mesh_sha256": mesh_hash},
            )
    finally:
        segmentation_store.case_store = original


def test_engine_does_not_fabricate_fdi_or_shared_confidence() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "synthetic_segmentation_arch.obj"
    import trimesh

    mesh = trimesh.load(fixture, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    labels = np.zeros(len(vertices), dtype=np.int64)
    labels[len(vertices) // 2 :] = 1
    raw = ToothInstanceNetRawOutput(
        instance_labels=labels,
        class_labels=np.array([], dtype=np.int64),
        class_confidences=np.array([], dtype=np.float32),
        original_vertices=vertices,
        original_faces=faces,
        transformed_points=vertices,
        sampled_indices=np.arange(len(vertices), dtype=np.int64),
        checkpoint_sha256="a" * 64,
    )
    adapter = type("Adapter", (), {"model_name": "test", "model_version": "1"})()
    engine = ToothInstanceNetEngine(adapter, arch=ArchType.UPPER)
    result = engine._map(raw, str(fixture))
    assert all(tooth.identity is None for tooth in result.identification.teeth)
    assert all(tooth.semantic_label is None for tooth in result.identification.teeth)
    assert all(tooth.confidence_available is False for tooth in result.identification.teeth)
    assert all(item[1] is None for item in result.diagnostics.fdi_by_instance)
    assert result.diagnostics.clinical_accuracy_claim is False


def test_get_segmentation_record_round_trip_matches_store(tmp_path: Path) -> None:
    store = InMemoryCaseStore(tmp_path / "cases.json")
    case = Case(
        id="case-round",
        patient_reference="",
        status=CaseStatus.CREATED,
        created_at=datetime.now(UTC),
    )
    store.add(case)
    import app.segmentation_store as segmentation_store

    original = segmentation_store.case_store
    segmentation_store.case_store = store
    try:
        begin_segmentation_record(
            "case-round",
            job_id="job",
            input_hash="e" * 64,
            processing_mode="real_case",
        )
        stored = get_segmentation_record("case-round")
        assert stored is not None
        assert stored["status"] == "processing"
        assert stored["input_hash"] == "e" * 64
    finally:
        segmentation_store.case_store = original
