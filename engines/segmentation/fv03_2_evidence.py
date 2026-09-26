"""FV-03.2 real segmentation evidence gate and provenance foundation.

Extends FV-03.1 seals. Does not import PyTorch or pointops. Does not fabricate
FDI, clinical accuracy, confidence, or ground-truth scores. The Colab
preprocessing reproducibility JSON is referenced immutably and never rewritten.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from domain.tooth.segmentation_review import (
    SEMANTIC_IDENTITY_NOT_ESTABLISHED,
    validate_segmentation_run,
)
from engines.segmentation.fv03_1_runtime import (
    PINNED_CHECKPOINT_SHA256,
    build_evidence_bundle,
    quality_evaluation,
    seal_evidence_bundle,
)
from engines.validation.geometric_engine import validate_mesh_geometry

RUN_CONTRACT_VERSION = "fv03.2-run-1"
EVIDENCE_GATE_VERSION = "fv03.2-evidence-gate-1"
EXTERNAL_EVIDENCE_VERSION = "fv03.2-external-evidence-1"
IMMUTABLE_RUN_STATUSES = frozenset({"completed", "blocked", "failed", "INVALID", "STALE"})
EXECUTION_ORIGINS = frozenset({"LOCAL_NATIVE", "EXTERNAL_CUDA", "SIMULATED", "UNKNOWN"})
GENUINE_INFERENCE_ORIGINS = frozenset({"LOCAL_NATIVE", "EXTERNAL_CUDA"})
_EXTERNAL_RUNTIME_FIELDS = (
    "execution_host",
    "execution_device",
    "gpu_model",
    "python_version",
    "pytorch_version",
    "cuda_version",
    "pointops_identity",
)
EXTERNAL_RUNTIME_FIELDS = _EXTERNAL_RUNTIME_FIELDS

# Verified Colab seed is metadata, not the only allowed production seed.
VERIFIED_PREPROCESSING_SEED_EXAMPLE = 123456
PREDICTION_PREPROCESSING_PIPELINE = (
    "ZScoreNormalize(norm=True)",
    "PoseNormalize(clean=True)",
    "InstanceCentroids",
    "UniformDensityDownsample(0.025)",
    "XYZAsFeatures",
    "NormalAsFeatures",
    "ToTensor",
)
PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE = (
    "fv032_exact_repository_preprocessing_reproducibility.json"
)
_REPO_ROOT = Path(__file__).resolve().parents[2]


def preprocessing_configuration(
    *,
    rng_seed: int | None = None,
    pipeline: tuple[str, ...] | list[str] | None = None,
    voxel_size: float = 0.025,
    executed: bool = False,
) -> dict[str, Any]:
    """Record preprocessing as run metadata. Seed is configuration, not a hard pin."""
    steps = list(pipeline) if pipeline is not None else list(PREDICTION_PREPROCESSING_PIPELINE)
    return {
        "pipeline": steps,
        "uniform_density_voxel_size": voxel_size,
        "rng_seed": rng_seed,
        "rng_seed_status": "RECORDED" if rng_seed is not None else "NOT_AVAILABLE",
        "verified_reproducibility_seed_example": VERIFIED_PREPROCESSING_SEED_EXAMPLE,
        "executed": bool(executed),
        "values": None if not executed else {"voxel_size": voxel_size, "rng_seed": rng_seed},
    }


def preprocessing_reproducibility_evidence_reference(
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Read-only reference to the immutable Colab reproducibility JSON.

    Never mutates, recreates, or substitutes the evidence file.
    """
    root = repo_root or _REPO_ROOT
    path = root / PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE
    if not path.is_file():
        return {
            "path": PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE,
            "present": False,
            "status": "NOT_AVAILABLE",
            "immutable": True,
            "mutated": False,
            "clinical_accuracy": "NOT_ESTABLISHED",
            "fdi_mapping": "NOT_ESTABLISHED",
            "ground_truth_segmentation_quality": "NOT_ESTABLISHED",
            "doctor_clinical_approval": "NOT_ESTABLISHED",
            "file_sha256": None,
            "seed": None,
            "upper_exact_reproducible": None,
            "lower_exact_reproducible": None,
        }
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode())
    upper = payload.get("upper") if isinstance(payload.get("upper"), dict) else {}
    lower = payload.get("lower") if isinstance(payload.get("lower"), dict) else {}
    return {
        "path": PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE,
        "present": True,
        "status": payload.get("status"),
        "immutable": True,
        "mutated": False,
        "clinical_accuracy": "NOT_ESTABLISHED",
        "fdi_mapping": "NOT_ESTABLISHED",
        "ground_truth_segmentation_quality": "NOT_ESTABLISHED",
        "doctor_clinical_approval": "NOT_ESTABLISHED",
        "file_sha256": digest,
        "seed": payload.get("seed"),
        "prediction_pipeline": payload.get("prediction_pipeline"),
        "upper_exact_reproducible": upper.get("exact_reproducible"),
        "lower_exact_reproducible": lower.get("exact_reproducible"),
        "model_changed": payload.get("model_changed"),
        "checkpoint_changed": payload.get("checkpoint_changed"),
        "thresholds_changed": payload.get("thresholds_changed"),
        "kernel_changed": payload.get("kernel_changed"),
        "fixed_seed_only": payload.get("fixed_seed_only"),
        "proves": [
            "repository_preprocessing_fixed_seed_reproducibility",
        ],
        "does_not_prove": [
            "clinical_accuracy",
            "fdi_correctness",
            "clinical_confidence",
            "ground_truth_segmentation_quality",
            "doctor_acceptance",
            "clinical_approval",
        ],
    }


def assert_preprocessing_evidence_unmutated(
    *,
    repo_root: Path | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Confirm the evidence file is present and optionally matches a known digest."""
    reference = preprocessing_reproducibility_evidence_reference(repo_root=repo_root)
    if not reference["present"]:
        raise FileNotFoundError(PREPROCESSING_REPRODUCIBILITY_EVIDENCE_RELATIVE)
    if expected_sha256 is not None and reference["file_sha256"] != expected_sha256:
        raise ValueError("Preprocessing reproducibility evidence digest mismatch.")
    return reference


def model_class_summary(instances: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize raw model classes without mapping them to FDI."""
    classes: dict[str, int] = {}
    for instance in instances:
        raw = instance.get("raw_model_class")
        key = "NOT_AVAILABLE" if raw is None else str(raw)
        classes[key] = classes.get(key, 0) + 1
    return {
        "instance_count": len(instances),
        "model_class_counts": classes,
        "model_class_is_fdi": False,
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "fdi_assigned": False,
    }


def confidence_summary(instances: list[dict[str, Any]]) -> dict[str, Any]:
    """Record confidence only when the model contract supplied it."""
    values = [
        item.get("confidence")
        for item in instances
        if item.get("confidence_available") and item.get("confidence") is not None
    ]
    return {
        "confidence_available": bool(values),
        "count_with_confidence": len(values),
        "values": values if values else None,
        "clinical_confidence": "NOT_ESTABLISHED",
        "label": "model_confidence" if values else "NOT_AVAILABLE",
    }


def validate_prepared_input_sha(
    *,
    prepared_sha256: str | None,
    expected_prepared_sha256: str | None,
) -> dict[str, Any]:
    if not prepared_sha256 or not expected_prepared_sha256:
        return {
            "passed": False,
            "status": "INVALID",
            "reason": "prepared_sha_missing",
        }
    if prepared_sha256 != expected_prepared_sha256:
        return {
            "passed": False,
            "status": "INVALID",
            "reason": "prepared_sha_mismatch",
            "prepared_sha256": prepared_sha256,
            "expected_prepared_sha256": expected_prepared_sha256,
        }
    return {
        "passed": True,
        "status": "MATCH",
        "prepared_sha256": prepared_sha256,
        "expected_prepared_sha256": expected_prepared_sha256,
    }


def refuse_fabricated_checkpoint_sha(model_sha256: str | None, *, real_inference: bool) -> dict[str, Any]:
    """Missing checkpoint SHA stays unavailable; it is never invented."""
    if model_sha256:
        matches = model_sha256 == PINNED_CHECKPOINT_SHA256
        return {
            "model_sha256": model_sha256,
            "status": "RECORDED",
            "matches_pinned_checkpoint": matches,
            "fabricated": False,
        }
    if real_inference:
        return {
            "model_sha256": None,
            "status": "INVALID",
            "matches_pinned_checkpoint": False,
            "fabricated": False,
            "reason": "checkpoint_sha_missing",
        }
    return {
        "model_sha256": None,
        "status": "NOT_AVAILABLE",
        "matches_pinned_checkpoint": False,
        "fabricated": False,
    }


def validate_segmentation_geometry_gate(
    *,
    run: dict[str, Any],
    face_count: int | None,
    finite: bool | None,
    prepared_vertices: np.ndarray | None = None,
    prepared_faces: np.ndarray | None = None,
) -> dict[str, Any]:
    """Combine segmentation run checks with GeometricValidationEngine topology rules.

    Invalid output is flagged. Geometry is never silently repaired.
    """
    technical = validate_segmentation_run(run, face_count=face_count, finite=finite)
    reasons = list(technical.get("reasons") or [])
    mesh_checks: list[dict[str, Any]] = []
    if prepared_vertices is not None and prepared_faces is not None:
        for instance in run.get("instances") or []:
            face_indices = list((instance.get("geometry_ref") or {}).get("face_indices") or [])
            if not face_indices:
                reasons.append("empty_instance_geometry")
                continue
            if any(index < 0 or index >= len(prepared_faces) for index in face_indices):
                reasons.append("face_index_out_of_range")
                continue
            subset = np.asarray(prepared_faces, dtype=np.int64)[face_indices]
            check = validate_mesh_geometry(prepared_vertices, subset)
            mesh_checks.append(
                {
                    "instance_id": instance.get("instance_id"),
                    **check,
                }
            )
            if not check["passed"]:
                reasons.append(f"invalid_geometry:{check['reason']}")
    unique = list(dict.fromkeys(reasons))
    passed = not unique
    status = "PASSED" if passed else "INVALID"
    report = {
        "engine": "GeometricValidationEngine.validate_mesh_geometry",
        "technical_validation": technical,
        "mesh_checks": mesh_checks,
        "passed": passed,
        "status": status,
        "reasons": unique,
        "repaired": False,
        "clinical_validation": False,
        "reviewable": bool(passed and run.get("status") == "completed" and not run.get("blocked")),
    }
    run["technical_validation"] = {
        "passed": passed,
        "reasons": unique,
        "clinical_validation": False,
        "reviewable": report["reviewable"],
        "geometric_validation": report,
    }
    run["reviewable"] = report["reviewable"]
    run["validation_status"] = status
    return report


def build_segmentation_run_contract(
    *,
    run_id: str,
    case_id: str,
    prepared_input_artifact_id: str | None,
    prepared_input_sha256: str | None,
    prepared_mesh_statistics: dict[str, Any],
    model_identifier: str | None,
    checkpoint_sha256: str | None,
    model_version: str | None,
    backend_name: str,
    backend_version: str,
    python_version: str | None,
    pytorch_version: str | None,
    cuda_version: str | None,
    pointops_identity: str | None,
    execution_device: str | None,
    preprocessing: dict[str, Any],
    inference_duration_ms: float | None,
    peak_rss_bytes: int | None,
    peak_gpu_memory_bytes: int | None,
    raw_model_output_reference: str | None,
    instance_clustering_parameters: dict[str, Any] | None,
    instances: list[dict[str, Any]],
    deterministic_validation: dict[str, Any],
    evidence_bundle_sha256: str | None,
    immutable_run_status: str,
    real_inference: bool,
    created_at: str | None = None,
    execution_origin: str = "UNKNOWN",
) -> dict[str, Any]:
    """Build the FV-03.2 run contract. Unavailable fields stay null / NOT_AVAILABLE."""
    checkpoint = refuse_fabricated_checkpoint_sha(
        checkpoint_sha256, real_inference=real_inference
    )
    status = immutable_run_status if immutable_run_status in IMMUTABLE_RUN_STATUSES else "INVALID"
    return {
        "contract_version": RUN_CONTRACT_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "prepared_input_artifact_id": prepared_input_artifact_id,
        "prepared_input_sha256": prepared_input_sha256,
        "prepared_mesh_statistics": prepared_mesh_statistics,
        "model_identifier": model_identifier,
        "checkpoint_sha256": checkpoint["model_sha256"],
        "checkpoint_status": checkpoint["status"],
        "model_version": model_version,
        "backend": {"name": backend_name, "version": backend_version},
        "python_version": python_version,
        "pytorch_version": pytorch_version,
        "cuda_version": cuda_version,
        "pointops_identity": pointops_identity,
        "execution_device": execution_device if real_inference else None,
        "preprocessing": preprocessing,
        "rng_seed": preprocessing.get("rng_seed"),
        "inference_duration_ms": inference_duration_ms if real_inference else None,
        "peak_rss_bytes": peak_rss_bytes,
        "peak_gpu_memory_bytes": peak_gpu_memory_bytes if real_inference else None,
        "raw_model_output_reference": raw_model_output_reference,
        "instance_clustering_parameters": instance_clustering_parameters,
        "output_instance_count": len(instances),
        "per_instance_model_class": [
            {
                "instance_id": item.get("instance_id"),
                "raw_model_class": item.get("raw_model_class"),
                "model_class_is_fdi": False,
                "confidence": item.get("confidence") if item.get("confidence_available") else None,
                "confidence_available": bool(item.get("confidence_available")),
            }
            for item in instances
        ],
        "model_class_summary": model_class_summary(instances),
        "confidence_summary": confidence_summary(instances),
        "deterministic_validation": deterministic_validation,
        "evidence_bundle_sha256": evidence_bundle_sha256,
        "created_at": created_at or datetime.now(UTC).isoformat(),
        "immutable_run_status": status,
        "real_inference": bool(real_inference),
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "fdi_assigned": False,
        "clinically_verified": False,
        "clinical_accuracy": "NOT_ESTABLISHED",
        "quality_evaluation": "NOT_AVAILABLE",
        "doctor_clinical_approval": "NOT_ESTABLISHED",
        "execution_origin": execution_origin if execution_origin in EXECUTION_ORIGINS else "UNKNOWN",
        "native_execution": execution_origin == "LOCAL_NATIVE" and bool(real_inference),
    }


def build_fv03_2_evidence_bundle(
    *,
    run_id: str,
    case_id: str,
    prepared_input_sha256: str | None,
    input_mesh: dict[str, Any],
    model_sha256: str | None,
    backend_name: str,
    backend_version: str,
    runtime_manifest: dict[str, Any] | None,
    device: str | None,
    preprocessing: dict[str, Any],
    inference_duration_ms: float | None,
    peak_rss_bytes: int | None,
    peak_gpu_memory_bytes: int | None,
    raw_model_output_reference: str | None,
    instance_generation: dict[str, Any] | None,
    instances: list[dict[str, Any]],
    technical_validation: dict[str, Any],
    real_inference: bool,
    blocked: bool,
    blocker: dict[str, Any] | None,
    inference_kind: str,
    run_contract: dict[str, Any] | None = None,
    sealed_at: str | None = None,
) -> dict[str, Any]:
    """Immutable, deterministically hashable evidence bundle for FV-03.2."""
    reproducibility = preprocessing_reproducibility_evidence_reference()
    quality = quality_evaluation(ground_truth_present=False)
    base = build_evidence_bundle(
        run_id=run_id,
        case_id=case_id,
        prepared_input_sha256=prepared_input_sha256,
        input_mesh=input_mesh,
        model_sha256=model_sha256,
        backend_name=backend_name,
        backend_version=backend_version,
        runtime_manifest=runtime_manifest,
        device=device,
        preprocessing_executed=bool(preprocessing.get("executed")),
        inference_duration_ms=inference_duration_ms,
        peak_memory_bytes=peak_rss_bytes,
        raw_model_output_reference=raw_model_output_reference,
        instance_generation=instance_generation,
        output_statistics={
            "instance_count": 0 if blocked else len(instances),
            "model_class_summary": model_class_summary(instances if not blocked else []),
            "confidence_summary": confidence_summary(instances if not blocked else []),
        },
        technical_validation=technical_validation,
        real_inference=real_inference,
        blocked=blocked,
        blocker=blocker,
        inference_kind=inference_kind,
    )
    # Rebuild once with FV-03.2 fields so the digest includes them.
    material = {
        key: value
        for key, value in base.items()
        if key not in {"evidence_sha256", "immutable"}
    }
    material["evidence_gate_version"] = EVIDENCE_GATE_VERSION
    material["preprocessing_parameters"] = preprocessing
    material["peak_rss_bytes"] = peak_rss_bytes
    material["peak_gpu_memory_bytes"] = peak_gpu_memory_bytes if real_inference else None
    material["instance_summary"] = model_class_summary(instances if not blocked else [])
    material["model_semantic_class_summary"] = material["instance_summary"]
    material["genuine_confidence"] = confidence_summary(instances if not blocked else [])
    material["run_manifest"] = copy.deepcopy(run_contract) if run_contract is not None else None
    material["input_provenance"] = {
        "prepared_input_sha256": prepared_input_sha256,
        "input_mesh": input_mesh,
    }
    material["model_provenance"] = {
        "model_sha256": model_sha256,
        "backend": {"name": backend_name, "version": backend_version},
        "runtime_manifest": runtime_manifest,
        "checkpoint_fabricated": False,
    }
    material["preprocessing_reproducibility_evidence"] = {
        "path": reproducibility.get("path"),
        "file_sha256": reproducibility.get("file_sha256"),
        "status": reproducibility.get("status"),
        "seed": reproducibility.get("seed"),
        "immutable": True,
        "clinical_accuracy": "NOT_ESTABLISHED",
    }
    material["quality_evaluation"] = quality
    material["deterministic_validation_findings"] = technical_validation
    material["original_model_output_immutable"] = True
    if sealed_at is not None:
        material["sealed_at"] = sealed_at
    return seal_evidence_bundle(material)


def canonical_json_bytes(payload: Any) -> bytes:
    """Canonical JSON. Key order is sorted. Timestamps are not added here."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()


def sha256_canonical(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def canonical_raw_model_output(instances: list[dict[str, Any]]) -> dict[str, Any]:
    """Stable raw-output identity. Confidence is kept only when the model supplied it."""
    rows = []
    for item in instances:
        available = bool(item.get("confidence_available"))
        rows.append(
            {
                "instance_id": item.get("instance_id"),
                "face_indices": [int(index) for index in (item.get("face_indices") or [])],
                "raw_model_class": item.get("raw_model_class"),
                "model_class_is_fdi": False,
                "confidence": item.get("confidence") if available else None,
                "confidence_available": available,
                "confidence_label": "model_confidence" if available else "NOT_AVAILABLE",
            }
        )
    rows.sort(key=lambda row: str(row.get("instance_id")))
    return {"schema": "fv03.2-raw-output-1", "instances": rows}


def _present_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def evaluate_external_inference_seal(
    payload: dict[str, Any],
    *,
    case_id: str,
    prepared_artifact_present: bool,
    prepared_sha256: str | None,
    prepared_vertices: np.ndarray | None,
    prepared_faces: np.ndarray | None,
    source_sha256: str | None,
) -> dict[str, Any]:
    """Validate an imported external inference bundle. The server decides seal status.

    A client field named verified is ignored. This function does not execute a model,
    does not invent instances, and does not rewrite the preprocessing evidence file.
    """
    blockers: list[str] = []
    origin = payload.get("execution_origin")
    if origin not in EXECUTION_ORIGINS:
        blockers.append("execution_origin_invalid")
        origin = "UNKNOWN"
    if origin == "LOCAL_NATIVE" or payload.get("local_native") is True or payload.get("native_execution") is True:
        blockers.append("external_import_cannot_become_local_native")
    if origin == "SIMULATED" or payload.get("inference_kind") == "mock_contract":
        blockers.append("simulated_is_not_real_inference")
    if origin == "UNKNOWN":
        blockers.append("unknown_origin_is_not_genuine_inference")
    if origin != "EXTERNAL_CUDA":
        blockers.append("execution_origin_not_external_cuda")

    runtime: dict[str, Any] = {}
    for field in _EXTERNAL_RUNTIME_FIELDS:
        text = _present_text(payload.get(field))
        runtime[field] = text
        if origin == "EXTERNAL_CUDA" and text is None:
            blockers.append(f"{field}_missing")

    claims_reference = payload.get("claims_reference_checkpoint", True)
    checkpoint_sha = _present_text(payload.get("checkpoint_sha256"))
    if checkpoint_sha is None:
        blockers.append("checkpoint_sha_missing")
    elif claims_reference and checkpoint_sha != PINNED_CHECKPOINT_SHA256:
        blockers.append("checkpoint_sha_mismatch")

    if payload.get("case_id") not in {None, case_id}:
        blockers.append("case_id_mismatch")
    if not payload.get("run_id"):
        blockers.append("run_id_missing")
    if not prepared_artifact_present or not prepared_sha256:
        blockers.append("prepared_artifact_missing")
    elif payload.get("prepared_input_sha256") != prepared_sha256:
        blockers.append("prepared_sha_mismatch")

    preprocessing = payload.get("preprocessing") if isinstance(payload.get("preprocessing"), dict) else {}
    pipeline = list(preprocessing.get("pipeline") or [])
    if not pipeline:
        blockers.append("preprocessing_missing")
    seed = payload.get("rng_seed")
    if seed is None and isinstance(preprocessing.get("rng_seed"), int):
        seed = preprocessing.get("rng_seed")
    reproducibility_claimed = bool(payload.get("reproducibility_claimed"))
    if reproducibility_claimed and not isinstance(seed, int):
        blockers.append("reproducibility_seed_missing")
    if (
        reproducibility_claimed
        and pipeline
        and isinstance(seed, int)
        and checkpoint_sha
        and prepared_sha256
        and payload.get("prepared_input_sha256") == prepared_sha256
    ):
        reproducibility_status = "REPRODUCIBLE"
    elif reproducibility_claimed:
        reproducibility_status = "NOT_REPRODUCIBLE"
    else:
        reproducibility_status = "NOT_AVAILABLE"

    raw = payload.get("raw_model_output")
    raw_instances = raw.get("instances") if isinstance(raw, dict) else None
    if not isinstance(raw_instances, list) or not raw_instances:
        blockers.append("raw_output_missing")
        canonical_raw: dict[str, Any] | None = None
        raw_sha = None
    else:
        try:
            canonical_raw = canonical_raw_model_output(raw_instances)
        except (TypeError, ValueError):
            canonical_raw = None
            blockers.append("raw_output_invalid")
        raw_sha = sha256_canonical(canonical_raw) if canonical_raw is not None else None
        if raw_sha is None or payload.get("raw_output_sha256") != raw_sha:
            blockers.append("raw_output_sha_mismatch")

    structural_reasons: list[str] = []
    specs = list((canonical_raw or {}).get("instances") or [])
    seen: set[str] = set()
    for item in specs:
        instance_id = str(item.get("instance_id") or "")
        if not instance_id or instance_id in seen:
            structural_reasons.append("duplicate_instance_id")
        seen.add(instance_id)
        if item.get("raw_model_class") is not None and not isinstance(item.get("raw_model_class"), int):
            structural_reasons.append("model_class_not_raw")
        faces = item.get("face_indices") or []
        if not faces:
            structural_reasons.append("empty_instance_geometry")
    if any(isinstance(source, dict) and source.get("fdi") is not None for source in (raw_instances or [])):
        structural_reasons.append("fdi_present")
    if any(
        isinstance(source, dict)
        and source.get("confidence") is not None
        and not source.get("confidence_available")
        for source in (raw_instances or [])
    ):
        structural_reasons.append("fake_confidence")
    blockers.extend(structural_reasons)

    face_count = int(len(prepared_faces)) if prepared_faces is not None else None
    finite = None
    if prepared_vertices is not None and getattr(prepared_vertices, "size", 0):
        finite = bool(np.isfinite(prepared_vertices).all())
    mesh_reasons: list[str] = []
    if prepared_vertices is None or prepared_faces is None:
        mesh_reasons.append("prepared_geometry_unavailable")
    else:
        for item in specs:
            indices = list(item.get("face_indices") or [])
            if face_count is not None and any(index < 0 or index >= face_count for index in indices):
                mesh_reasons.append("face_index_out_of_range")
                continue
            subset = np.asarray(prepared_faces, dtype=np.int64)[indices]
            check = validate_mesh_geometry(prepared_vertices, subset)
            if not check["passed"]:
                mesh_reasons.append(f"invalid_geometry:{check['reason']}")
    blockers.extend(mesh_reasons)
    unique_blockers = list(dict.fromkeys(blockers))
    geometry_passed = not mesh_reasons and not structural_reasons and finite is not False
    validation_status = "PASSED" if geometry_passed and not unique_blockers else "INVALID"
    sealed = not unique_blockers
    real_inference = sealed and origin == "EXTERNAL_CUDA"
    validation = {
        "engine": "GeometricValidationEngine.validate_mesh_geometry",
        "passed": geometry_passed and sealed,
        "status": "PASSED" if sealed else validation_status,
        "reasons": unique_blockers,
        "repaired": False,
        "clinical_validation": False,
    }
    clustering = payload.get("instance_clustering") if isinstance(payload.get("instance_clustering"), dict) else None
    identity = {
        "evidence_version": EXTERNAL_EVIDENCE_VERSION,
        "run_id": payload.get("run_id"),
        "case_id": case_id,
        "execution_origin": "EXTERNAL_CUDA" if sealed else origin,
        "native_execution": False,
        "local_native": False,
        "runtime": runtime,
        "model_identifier": payload.get("model_identifier"),
        "checkpoint_sha256": checkpoint_sha,
        "claims_reference_checkpoint": bool(claims_reference),
        "model_version": payload.get("model_version"),
        "prepared_input_artifact_id": payload.get("prepared_input_artifact_id") or prepared_sha256,
        "prepared_input_sha256": prepared_sha256 if sealed else payload.get("prepared_input_sha256"),
        "source_sha256": source_sha256,
        "preprocessing": {
            "pipeline": pipeline,
            "rng_seed": seed if isinstance(seed, int) else None,
            "rng_seed_status": "RECORDED" if isinstance(seed, int) else "NOT_AVAILABLE",
        },
        "reproducibility_status": reproducibility_status,
        "inference_duration_ms": payload.get("inference_duration_ms"),
        "peak_gpu_memory_bytes": payload.get("peak_gpu_memory_bytes"),
        "raw_output_sha256": raw_sha,
        "instance_clustering": clustering,
        "output_instance_count": len(specs),
        "model_class_summary": model_class_summary(
            [
                {
                    "raw_model_class": item.get("raw_model_class"),
                    "confidence": item.get("confidence"),
                    "confidence_available": item.get("confidence_available"),
                }
                for item in specs
            ]
        ),
        "confidence_summary": confidence_summary(
            [
                {
                    "confidence": item.get("confidence"),
                    "confidence_available": item.get("confidence_available"),
                }
                for item in specs
            ]
        ),
        "deterministic_validation": {
            "passed": validation["passed"],
            "status": validation["status"],
            "reasons": unique_blockers,
            "repaired": False,
        },
        "real_inference": real_inference,
        "inference_executed_by_this_process": False,
        "clinically_verified": False,
        "clinical_accuracy": "NOT_ESTABLISHED",
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "fdi_assigned": False,
        "quality_evaluation": "NOT_AVAILABLE",
    }
    # A failed seal is not hashed as a verified bundle.
    evidence = None
    evidence_sha = None
    if sealed:
        evidence_sha = sha256_canonical(identity)
        evidence = {
            **identity,
            "immutable": True,
            "sealed": True,
            "evidence_sha256": evidence_sha,
            "original_model_output_immutable": True,
            "raw_model_output": canonical_raw,
        }
    return {
        "sealed": sealed,
        "blockers": unique_blockers,
        "primary_blocker": unique_blockers[0] if unique_blockers else None,
        "execution_origin": "EXTERNAL_CUDA" if sealed else origin,
        "native_execution": False,
        "local_native": False,
        "real_inference": real_inference,
        "inference_executed_by_this_process": False,
        "clinically_verified": False,
        "clinical_accuracy": "NOT_ESTABLISHED",
        "quality_evaluation": "NOT_AVAILABLE",
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "fdi_assigned": False,
        "validation_status": "PASSED" if sealed else "INVALID",
        "validation": validation,
        "reproducibility_status": reproducibility_status,
        "ignored_client_verified": "verified" in payload,
        "evidence": evidence,
        "evidence_sha256": evidence_sha,
        "raw_model_output": canonical_raw,
        "instance_specs": specs,
        "checkpoint_sha256": checkpoint_sha,
        "prepared_input_sha256": prepared_sha256,
        "source_sha256": source_sha256,
        "runtime": runtime,
        "preprocessing": identity["preprocessing"],
        "model_version": payload.get("model_version"),
        "model_identifier": payload.get("model_identifier"),
        "instance_clustering": clustering,
        "inference_duration_ms": payload.get("inference_duration_ms") if sealed else None,
        "peak_gpu_memory_bytes": payload.get("peak_gpu_memory_bytes") if sealed else None,
    }


def external_evidence_intact(bundle: dict[str, Any] | None) -> bool:
    """Recompute the canonical identity hash. Timestamps are not part of identity."""
    if not isinstance(bundle, dict) or not bundle.get("immutable"):
        return False
    identity = {
        key: value
        for key, value in bundle.items()
        if key
        not in {
            "evidence_sha256",
            "immutable",
            "sealed",
            "original_model_output_immutable",
            "raw_model_output",
        }
    }
    return bundle.get("evidence_sha256") == sha256_canonical(identity) and bool(bundle.get("sealed"))


def evidence_bundle_digest(bundle: dict[str, Any]) -> str:
    """Return the sealed digest; recompute if needed for comparison helpers."""
    digest = bundle.get("evidence_sha256")
    if isinstance(digest, str) and digest:
        return digest
    resealed = seal_evidence_bundle(
        {key: value for key, value in bundle.items() if key != "evidence_sha256"}
    )
    return str(resealed["evidence_sha256"])
