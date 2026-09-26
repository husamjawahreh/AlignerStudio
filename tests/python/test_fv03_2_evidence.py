"""FV-03.2 real segmentation evidence gate and provenance foundation tests.

Does not execute ToothInstanceNet. Does not fabricate clinical accuracy or FDI.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import trimesh

from domain.tooth.segmentation_review import (
    SEMANTIC_IDENTITY_NOT_ESTABLISHED,
    candidate_instance,
)
from engines.geometry.intake_inspection import inspect_source_file
from engines.geometry.scan_preparation import accept_preparation, apply_operation
from engines.segmentation.fv03_1_runtime import evidence_intact, quality_evaluation
from engines.segmentation.fv03_2_evidence import (
    PREDICTION_PREPROCESSING_PIPELINE,
    PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE,
    VERIFIED_PREPROCESSING_SEED_EXAMPLE,
    assert_preprocessing_evidence_unmutated,
    build_fv03_2_evidence_bundle,
    build_segmentation_run_contract,
    preprocessing_configuration,
    preprocessing_reproducibility_evidence_reference,
    refuse_fabricated_checkpoint_sha,
    validate_prepared_input_sha,
    validate_segmentation_geometry_gate,
)
from engines.segmentation.fv03_pipeline import (
    DeterministicMockBackend,
    reset_segmentation_jobs,
    review_segmentation,
    run_segmentation_job,
    submit_segmentation_job,
)
from engines.validation.geometric_engine import validate_mesh_geometry


@pytest.fixture(autouse=True)
def _clear_jobs() -> None:
    reset_segmentation_jobs()
    yield
    reset_segmentation_jobs()


def _box(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trimesh.creation.box().export(path)


def _accepted(path: Path) -> dict:
    artifact = inspect_source_file(
        path, case_id="case-1", explicit_arch="upper", original_filename=path.name
    )
    apply_operation(
        artifact,
        "orient",
        {"method": "user_transform", "rotation_deg": [0, 0, 90], "translation": [0, 0, 0]},
    )
    accept_preparation(artifact)
    return artifact


def _run_mock(artifact: dict) -> dict:
    queued = submit_segmentation_job(
        artifact,
        case_id="case-1",
        arch="upper",
        backend=DeterministicMockBackend(),
        schedule=False,
    )
    finished = run_segmentation_job(queued["job_id"])
    assert finished is not None
    return finished


def _sample_instances(run_id: str, prepared_sha: str) -> list[dict]:
    return [
        candidate_instance(
            instance_id="inst-0",
            run_id=run_id,
            prepared_sha256=prepared_sha,
            face_indices=[0, 1],
            backend_name="toothinstancenet",
            backend_version="test",
            model_id="instseg_full.ckpt",
            model_sha256="100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803",
            raw_model_class=3,
            confidence=0.91,
            confidence_available=True,
            real_inference=True,
        ),
        candidate_instance(
            instance_id="inst-1",
            run_id=run_id,
            prepared_sha256=prepared_sha,
            face_indices=[2, 3],
            backend_name="toothinstancenet",
            backend_version="test",
            model_id="instseg_full.ckpt",
            model_sha256="100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803",
            raw_model_class=5,
            confidence=None,
            confidence_available=False,
            real_inference=True,
        ),
    ]


def test_genuine_model_prediction_carries_provenance(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    finished = _run_mock(artifact)
    run = artifact["segmentation"]["runs"][0]
    assert finished["state"] == "completed"
    assert run["run_contract"]["contract_version"] == "fv03.2-run-1"
    assert run["run_contract"]["run_id"] == run["run_id"]
    assert run["run_contract"]["prepared_input_sha256"] == run["prepared_sha256"]
    assert run["evidence"]["immutable"] is True
    assert run["evidence_bundle_sha256"] == run["evidence"]["evidence_sha256"]
    assert run["run_contract"]["semantic_identity"] == SEMANTIC_IDENTITY_NOT_ESTABLISHED
    assert run["run_contract"]["clinically_verified"] is False
    assert run["run_contract"]["clinical_accuracy"] == "NOT_ESTABLISHED"
    assert finished["evidence_bundle_sha256"] == run["evidence"]["evidence_sha256"]
    assert finished["requires_review"] is True
    assert finished["clinically_verified"] is False


def test_missing_checkpoint_sha_cannot_be_fabricated() -> None:
    absent = refuse_fabricated_checkpoint_sha(None, real_inference=True)
    assert absent["model_sha256"] is None
    assert absent["status"] == "INVALID"
    assert absent["fabricated"] is False
    blocked = refuse_fabricated_checkpoint_sha(None, real_inference=False)
    assert blocked["status"] == "NOT_AVAILABLE"
    assert blocked["fabricated"] is False
    contract = build_segmentation_run_contract(
        run_id="r1",
        case_id="c1",
        prepared_input_artifact_id="prep",
        prepared_input_sha256="abc",
        prepared_mesh_statistics={},
        model_identifier="instseg_full.ckpt",
        checkpoint_sha256=None,
        model_version=None,
        backend_name="toothinstancenet",
        backend_version="v",
        python_version=None,
        pytorch_version=None,
        cuda_version=None,
        pointops_identity=None,
        execution_device="cuda",
        preprocessing=preprocessing_configuration(),
        inference_duration_ms=1.0,
        peak_rss_bytes=None,
        peak_gpu_memory_bytes=None,
        raw_model_output_reference=None,
        instance_clustering_parameters=None,
        instances=[],
        deterministic_validation={"passed": True},
        evidence_bundle_sha256=None,
        immutable_run_status="completed",
        real_inference=True,
        created_at="2026-09-26T00:00:00+00:00",
    )
    assert contract["checkpoint_sha256"] is None
    assert contract["checkpoint_status"] == "INVALID"


def test_model_class_remains_distinct_from_fdi(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    _run_mock(artifact)
    instance = artifact["segmentation"]["review"]["instances"][0]
    assert instance["fdi"] is None
    assert instance["model_class_mapping"] == SEMANTIC_IDENTITY_NOT_ESTABLISHED
    assert artifact["segmentation"]["fdi_assigned"] is False
    summary = artifact["segmentation"]["runs"][0]["run_contract"]["model_class_summary"]
    assert summary["model_class_is_fdi"] is False
    assert summary["semantic_identity"] == SEMANTIC_IDENTITY_NOT_ESTABLISHED


def test_prepared_input_sha_mismatch_is_rejected() -> None:
    mismatch = validate_prepared_input_sha(
        prepared_sha256="aaa",
        expected_prepared_sha256="bbb",
    )
    assert mismatch["passed"] is False
    assert mismatch["status"] == "INVALID"
    assert mismatch["reason"] == "prepared_sha_mismatch"
    run = {
        "run_id": "r1",
        "prepared_sha256": "aaa",
        "source_sha256": "src",
        "input": {"prepared_sha256": "bbb"},
        "backend": {"name": "toothinstancenet", "model_sha256": None},
        "status": "completed",
        "blocked": False,
        "real_inference": False,
        "fixture": False,
        "fdi_assigned": False,
        "clinical_accuracy_claim": False,
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "instances": [],
    }
    report = validate_segmentation_geometry_gate(run=run, face_count=12, finite=True)
    assert report["passed"] is False
    assert "input_provenance" in report["reasons"]
    assert run["validation_status"] == "INVALID"


def test_invalid_geometry_is_flagged_by_geometric_validation_engine() -> None:
    vertices = np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float64)
    faces = np.asarray([[0, 1, 2]], dtype=np.int64)
    ok = validate_mesh_geometry(vertices, faces)
    assert ok["passed"] is True
    assert ok["repaired"] is False
    bad = validate_mesh_geometry(vertices, np.asarray([[0, 1, 9]], dtype=np.int64))
    assert bad["passed"] is False
    assert bad["reason"] == "face references an invalid vertex"
    nonfinite = validate_mesh_geometry(
        np.asarray([[0.0, 0.0, np.nan], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        faces,
    )
    assert nonfinite["passed"] is False
    prepared_sha = "prep"
    run = {
        "run_id": "r1",
        "prepared_sha256": prepared_sha,
        "source_sha256": "src",
        "input": {"prepared_sha256": prepared_sha},
        "backend": {"name": "mock", "model_sha256": None},
        "status": "completed",
        "blocked": False,
        "real_inference": False,
        "fixture": False,
        "fdi_assigned": False,
        "clinical_accuracy_claim": False,
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "instances": _sample_instances("r1", prepared_sha),
    }
    report = validate_segmentation_geometry_gate(
        run=run,
        face_count=1,
        finite=True,
        prepared_vertices=vertices,
        prepared_faces=faces,
    )
    assert report["passed"] is False
    assert report["repaired"] is False
    assert any("face_index" in reason or "invalid_geometry" in reason for reason in report["reasons"])


def test_doctor_modification_preserves_immutable_model_output(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    _run_mock(artifact)
    run = artifact["segmentation"]["runs"][0]
    model_faces = [
        list(item["geometry_ref"]["face_indices"])
        for item in artifact["segmentation"]["review"]["model_instances"]
    ]
    evidence_sha = run["evidence"]["evidence_sha256"]
    review_segmentation(
        artifact,
        "merge",
        {"instance_id": "inst-0", "other_instance_id": "inst-1"},
    )
    assert [
        list(item["geometry_ref"]["face_indices"])
        for item in artifact["segmentation"]["review"]["model_instances"]
    ] == model_faces
    assert evidence_intact(run["evidence"])
    assert run["evidence"]["evidence_sha256"] == evidence_sha
    assert run["evidence"]["original_model_output_immutable"] is True


def test_doctor_acceptance_is_not_clinical_verification(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    _run_mock(artifact)
    review_segmentation(artifact, "accept", {"instance_id": "inst-0"})
    accepted = next(
        item
        for item in artifact["segmentation"]["review"]["instances"]
        if item["instance_id"] == "inst-0"
    )
    assert accepted["review_state"] == "DOCTOR_ACCEPTED"
    assert accepted["truth_state"] != "VERIFIED"
    assert artifact["segmentation"]["runs"][0]["clinically_verified"] is False
    assert artifact["segmentation"]["clinical_accuracy_claim"] is False
    assert artifact["segmentation"]["runs"][0]["run_contract"]["doctor_clinical_approval"] == (
        "NOT_ESTABLISHED"
    )
    quality = artifact["segmentation"]["runs"][0]["quality_evaluation"]
    assert quality["quality_evaluation"] == "NOT_AVAILABLE"
    assert quality["clinical_accuracy"] == "NOT_ESTABLISHED"


def test_missing_reference_data_produces_quality_not_available() -> None:
    report = quality_evaluation(ground_truth_present=False, measurements={"dice": 0.99})
    assert report["quality_evaluation"] == "NOT_AVAILABLE"
    assert report["dice"] is None
    assert report["clinical_accuracy"] == "NOT_ESTABLISHED"
    bundle = build_fv03_2_evidence_bundle(
        run_id="r1",
        case_id="c1",
        prepared_input_sha256="abc",
        input_mesh={"vertex_count": 1},
        model_sha256=None,
        backend_name="mock",
        backend_version="v",
        runtime_manifest=None,
        device=None,
        preprocessing=preprocessing_configuration(),
        inference_duration_ms=None,
        peak_rss_bytes=None,
        peak_gpu_memory_bytes=None,
        raw_model_output_reference=None,
        instance_generation=None,
        instances=[],
        technical_validation={"passed": True},
        real_inference=False,
        blocked=True,
        blocker={"code": "ENVIRONMENT_UNAVAILABLE"},
        inference_kind="not_run",
        sealed_at="2026-09-26T00:00:00+00:00",
    )
    assert bundle["quality_evaluation"]["quality_evaluation"] == "NOT_AVAILABLE"


def test_evidence_bundle_hashing_is_deterministic() -> None:
    kwargs = dict(
        run_id="r1",
        case_id="c1",
        prepared_input_sha256="abc",
        input_mesh={"vertex_count": 8, "face_count": 12, "finite": True},
        model_sha256=None,
        backend_name="deterministic_mock",
        backend_version="fv03-mock-1",
        runtime_manifest={"python_version": "3.12.3"},
        device=None,
        preprocessing=preprocessing_configuration(rng_seed=123456),
        inference_duration_ms=None,
        peak_rss_bytes=None,
        peak_gpu_memory_bytes=None,
        raw_model_output_reference=None,
        instance_generation=None,
        instances=[],
        technical_validation={"passed": True, "reasons": []},
        real_inference=False,
        blocked=False,
        blocker=None,
        inference_kind="mock_contract",
        sealed_at="2026-09-26T12:00:00+00:00",
    )
    first = build_fv03_2_evidence_bundle(**kwargs)
    second = build_fv03_2_evidence_bundle(**kwargs)
    assert first["evidence_sha256"] == second["evidence_sha256"]
    assert evidence_intact(first)
    assert evidence_intact(second)


def test_repeated_identical_evidence_generation_same_hash() -> None:
    preprocessing = preprocessing_configuration(rng_seed=VERIFIED_PREPROCESSING_SEED_EXAMPLE)
    digests = [
        build_fv03_2_evidence_bundle(
            run_id="fixed",
            case_id="case",
            prepared_input_sha256="sha",
            input_mesh={},
            model_sha256=None,
            backend_name="mock",
            backend_version="1",
            runtime_manifest=None,
            device=None,
            preprocessing=preprocessing,
            inference_duration_ms=None,
            peak_rss_bytes=None,
            peak_gpu_memory_bytes=None,
            raw_model_output_reference=None,
            instance_generation=None,
            instances=[],
            technical_validation={"passed": True},
            real_inference=False,
            blocked=True,
            blocker={"code": "DRIVER_UNAVAILABLE"},
            inference_kind="not_run",
            sealed_at="2026-09-26T00:00:00+00:00",
        )["evidence_sha256"]
        for _ in range(3)
    ]
    assert digests[0] == digests[1] == digests[2]


def test_fixed_seed_preprocessing_metadata_is_represented() -> None:
    config = preprocessing_configuration(rng_seed=123456, executed=True)
    assert config["rng_seed"] == 123456
    assert config["rng_seed_status"] == "RECORDED"
    assert config["pipeline"] == list(PREDICTION_PREPROCESSING_PIPELINE)
    assert config["verified_reproducibility_seed_example"] == VERIFIED_PREPROCESSING_SEED_EXAMPLE
    other = preprocessing_configuration(rng_seed=42)
    assert other["rng_seed"] == 42
    assert other["verified_reproducibility_seed_example"] == 123456
    missing = preprocessing_configuration()
    assert missing["rng_seed"] is None
    assert missing["rng_seed_status"] == "NOT_AVAILABLE"


def test_colab_evidence_json_can_be_referenced_without_mutation() -> None:
    reference = preprocessing_reproducibility_evidence_reference()
    assert reference["present"] is True
    assert reference["path"] == PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE
    assert reference["status"] == "REPOSITORY_PREPROCESSING_FIXED_SEED_REPRODUCIBLE"
    assert reference["seed"] == 123456
    assert reference["upper_exact_reproducible"] is True
    assert reference["lower_exact_reproducible"] is True
    assert reference["immutable"] is True
    assert reference["mutated"] is False
    assert reference["clinical_accuracy"] == "NOT_ESTABLISHED"
    assert "clinical_accuracy" in reference["does_not_prove"]
    before = Path(PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE).read_bytes()
    before_sha = hashlib.sha256(before).hexdigest()
    assert_preprocessing_evidence_unmutated(expected_sha256=before_sha)
    after = Path(PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE).read_bytes()
    assert after == before
    assert json.loads(after.decode())["fixed_seed_only"] is True


def test_pipeline_run_records_preprocessing_reproducibility_reference(tmp_path: Path) -> None:
    path = tmp_path / "scan.stl"
    _box(path)
    artifact = _accepted(path)
    _run_mock(artifact)
    run = artifact["segmentation"]["runs"][0]
    evidence_ref = run["preprocessing_reproducibility_evidence"]
    assert evidence_ref["path"] == PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE
    assert evidence_ref["immutable"] is True
    assert run["preprocessing"]["pipeline"] == list(PREDICTION_PREPROCESSING_PIPELINE)
    assert run["evidence"]["preprocessing_reproducibility_evidence"]["clinical_accuracy"] == (
        "NOT_ESTABLISHED"
    )
    mutated = copy.deepcopy(run["evidence"])
    mutated["run_manifest"] = {"tampered": True}
    assert evidence_intact(mutated) is False
    assert evidence_intact(run["evidence"])
