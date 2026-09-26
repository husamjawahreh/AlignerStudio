"""FV-03.2 external CUDA inference runner contract.

This module prepares the bundle the Colab/A100 run must produce and, only when
explicitly executed on a CUDA host, calls the official TeethSegDataset
prediction preprocessing. It does not approximate that pipeline, does not
invent instances, and does not seal a run. Sealing stays on the server.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from adapters.toothinstancenet.contract import ToothInstanceNetConfig
from engines.segmentation.fv03_1_runtime import PINNED_CHECKPOINT_SHA256
from engines.segmentation.fv03_2_evidence import (
    EXTERNAL_RUNTIME_FIELDS,
    PREDICTION_PREPROCESSING_PIPELINE,
    VERIFIED_PREPROCESSING_SEED_EXAMPLE,
    canonical_raw_model_output,
    sha256_canonical,
)

BUNDLE_FILES = (
    "manifest.json",
    "runtime.json",
    "preprocessing.json",
    "model.json",
    "raw_output/instances.json",
    "validation.json",
    "evidence.json",
    "README.md",
)
OFFICIAL_PREPROCESSING = "teethland.data.datasets.TeethSegDataset"
FORBIDDEN_PREPROCESSING_SUBSTITUTE = "adapters.toothinstancenet.preprocessing.prepare_mesh"
FACE_ASSIGNMENT = "unanimous_vertex_instance_on_original_triangles"
INFERENCE_DETERMINISM = "NOT_CLAIMED"


def external_run_status() -> dict[str, Any]:
    """Repository readiness. This does not mean an inference was executed."""
    return {
        "READY_FOR_EXTERNAL_INFERENCE_RUN": True,
        "GENUINE_EXTERNAL_INFERENCE_COMPLETED": False,
        "preprocessing_implementation": OFFICIAL_PREPROCESSING,
        "preprocessing_forbidden_substitute": FORBIDDEN_PREPROCESSING_SUBSTITUTE,
        "prediction_pipeline": list(PREDICTION_PREPROCESSING_PIPELINE),
        "dataset_flags": {"norm": True, "clean": True, "with_color": False},
        "uniform_density_voxel_size": 0.025,
        "documented_reproducibility_seed": VERIFIED_PREPROCESSING_SEED_EXAMPLE,
        "seed_is_universal_default": False,
        "inference_determinism": INFERENCE_DETERMINISM,
        "execution_origin": "EXTERNAL_CUDA",
        "native_execution": False,
        "clinical_accuracy": "NOT_ESTABLISHED",
        "fdi_mapping": "NOT_ESTABLISHED",
        "quality_evaluation": "NOT_AVAILABLE",
        "doctor_clinical_approval": "NOT_ESTABLISHED",
    }


def model_configuration_record() -> dict[str, Any]:
    """Qualified DentalNet contract. This does not load weights."""
    config = ToothInstanceNetConfig(
        checkpoint_path=Path("instseg_full.ckpt"),
        checkpoint_sha256=PINNED_CHECKPOINT_SHA256,
    )
    return {
        "model_identifier": "instseg_full.ckpt",
        "model_name": config.model_name,
        "model_version": config.model_version,
        "checkpoint_sha256_expected": PINNED_CHECKPOINT_SHA256,
        "claims_reference_checkpoint": True,
        "in_channels": config.in_channels,
        "num_classes": config.num_classes,
        "fdi_encoded": False,
        "arch_encoded": False,
        "left_right_encoded": False,
        "model_class_is_fdi": False,
        "channels_list": list(config.channels_list),
        "depths": list(config.depths),
        "heads_list": list(config.heads_list),
        "window_sizes": list(config.window_sizes),
        "uniform_density_voxel_size": config.uniform_density_voxel_size,
        "zscore_std": config.zscore_std,
        "instance_clustering": {"algorithm": "learned_region_cluster"},
        "output_contract": {
            "instance_head": "offsets_and_sigmas",
            "seed_head": "seed_logit",
            "identify_head": "seven_logits",
            "instance_ids": "learned_region_cluster",
            "class_index_meaning": "model_semantic_class",
        },
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_external_import_payload(
    *,
    run_id: str,
    case_id: str,
    arch: str,
    prepared_input_sha256: str,
    checkpoint_sha256: str | None,
    runtime: dict[str, Any],
    rng_seed: int | None,
    reproducibility_claimed: bool,
    raw_instances: list[dict[str, Any]] | None,
    inference_duration_ms: float | None = None,
    peak_gpu_memory_bytes: int | None = None,
    model_version: str | None = None,
) -> dict[str, Any]:
    """Build the POST body. A client verified flag is never set."""
    instances = list(raw_instances or [])
    raw = {"instances": instances} if instances else None
    raw_sha = (
        sha256_canonical(canonical_raw_model_output(instances)) if instances else None
    )
    model = model_configuration_record()
    payload: dict[str, Any] = {
        "run_id": run_id,
        "case_id": case_id,
        "arch": arch,
        "execution_origin": "EXTERNAL_CUDA",
        "native_execution": False,
        "local_native": False,
        "inference_executed_by_this_process": False,
        "execution_host": runtime.get("execution_host"),
        "execution_device": runtime.get("execution_device"),
        "gpu_model": runtime.get("gpu_model"),
        "python_version": runtime.get("python_version"),
        "pytorch_version": runtime.get("pytorch_version"),
        "cuda_version": runtime.get("cuda_version"),
        "pointops_identity": runtime.get("pointops_identity"),
        "model_identifier": model["model_identifier"],
        "model_version": model_version or model["model_version"],
        "checkpoint_sha256": checkpoint_sha256,
        "claims_reference_checkpoint": True,
        "prepared_input_artifact_id": prepared_input_sha256,
        "prepared_input_sha256": prepared_input_sha256,
        "preprocessing": {
            "implementation": OFFICIAL_PREPROCESSING,
            "not_used": FORBIDDEN_PREPROCESSING_SUBSTITUTE,
            "pipeline": list(PREDICTION_PREPROCESSING_PIPELINE),
            "dataset_flags": {"norm": True, "clean": True, "with_color": False},
            "uniform_density_voxel_size": 0.025,
            "rng_seed": rng_seed,
        },
        "rng_seed": rng_seed,
        "reproducibility_claimed": reproducibility_claimed,
        "inference_determinism": INFERENCE_DETERMINISM,
        "inference_duration_ms": inference_duration_ms,
        "peak_gpu_memory_bytes": peak_gpu_memory_bytes,
        "raw_model_output": raw,
        "raw_output_sha256": raw_sha,
        "instance_clustering": {"algorithm": "learned_region_cluster"},
        "model_class_is_fdi": False,
        "clinical_accuracy": "NOT_ESTABLISHED",
        "fdi_assigned": False,
    }
    for field in EXTERNAL_RUNTIME_FIELDS:
        payload.setdefault(field, runtime.get(field))
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_blocked_bundle(output_dir: Path, *, blockers: list[str], detail: dict[str, Any]) -> dict[str, Any]:
    """Record a refused run. Does not invent raw instances or a seal."""
    output_dir.mkdir(parents=True, exist_ok=True)
    status = {
        **external_run_status(),
        "GENUINE_EXTERNAL_INFERENCE_COMPLETED": False,
        "sealable_candidate": False,
        "blockers": blockers,
        "detail": detail,
    }
    _write_json(output_dir / "status.json", status)
    _write_json(
        output_dir / "validation.json",
        {
            "server_seal": "NOT_RUN",
            "sealable_candidate": False,
            "blockers": blockers,
            "repaired": False,
        },
    )
    readme = output_dir / "README.md"
    readme.write_text(
        "External inference was not completed. No raw model output was written. "
        "Do not import this directory as a sealed run.\n",
        encoding="utf-8",
    )
    return status


def write_completed_bundle(
    output_dir: Path,
    *,
    payload: dict[str, Any],
    runtime: dict[str, Any],
    preprocessing: dict[str, Any],
    model: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    """Write the transfer bundle. evidence.json is the import body and has no timestamp."""
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = payload.get("raw_model_output") or {"instances": []}
    _write_json(output_dir / "raw_output" / "instances.json", raw)
    _write_json(output_dir / "runtime.json", runtime)
    _write_json(output_dir / "preprocessing.json", preprocessing)
    _write_json(output_dir / "model.json", model)
    _write_json(output_dir / "validation.json", validation)
    _write_json(output_dir / "evidence.json", payload)
    manifest = {
        "bundle_layout": list(BUNDLE_FILES),
        "prepared_input_sha256": payload.get("prepared_input_sha256"),
        "checkpoint_sha256": payload.get("checkpoint_sha256"),
        "raw_output_sha256": payload.get("raw_output_sha256"),
        "import_payload_sha256": sha256_canonical(payload),
        "execution_origin": "EXTERNAL_CUDA",
        "native_execution": False,
        "server_seal": "NOT_RUN",
        "clinical_accuracy": "NOT_ESTABLISHED",
        "fdi_assigned": False,
    }
    _write_json(output_dir / "manifest.json", manifest)
    (output_dir / "README.md").write_text(
        "Transfer this directory unchanged. Import evidence.json through "
        "POST /cases/{id}/uploads/{arch}/segmentation/external-evidence. "
        "The server decides the seal. This file is not a clinical result.\n",
        encoding="utf-8",
    )
    status = {
        **external_run_status(),
        "GENUINE_EXTERNAL_INFERENCE_COMPLETED": True,
        "sealable_candidate": bool(validation.get("sealable_candidate")),
        "server_seal": "NOT_RUN",
        "bundle_dir": str(output_dir),
    }
    _write_json(output_dir / "status.json", status)
    return status


def _nvcc_version() -> str | None:
    if shutil.which("nvcc") is None:
        return None
    try:
        completed = subprocess.run(
            ["nvcc", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        if "release" in line:
            return line.strip() or None
    return None


def _measure_runtime() -> dict[str, Any]:
    """Read the live process. Missing values stay None."""
    torch = None
    try:
        import torch as torch_module
    except ImportError:
        torch_module = None
    torch = torch_module
    pointops_identity = None
    try:
        import pointops
    except ImportError:
        pointops = None
    else:
        pointops_identity = getattr(pointops, "__file__", None) or "pointops"
    gpu_model = None
    cuda_version = None
    device = None
    capability = None
    if torch is not None and torch.cuda.is_available():
        gpu_model = torch.cuda.get_device_name(0)
        cuda_version = torch.version.cuda
        device = "cuda:0"
        major, minor = torch.cuda.get_device_capability(0)
        capability = f"{major}.{minor}"
    return {
        "execution_host": platform.node() or None,
        "execution_device": device,
        "gpu_model": gpu_model,
        "gpu_compute_capability": capability,
        "python_version": platform.python_version(),
        "pytorch_version": getattr(torch, "__version__", None) if torch is not None else None,
        "cuda_version": cuda_version,
        "pointops_identity": pointops_identity,
        "nvcc_version": _nvcc_version(),
        "inference_determinism": INFERENCE_DETERMINISM,
        "determinism_note": (
            "The explicit seed is recorded. CUDA kernel determinism is not claimed."
        ),
    }


def _official_dataset_item(mesh_path: Path, *, arch: str, seed: int) -> dict[str, Any]:
    """Run TeethSegDataset prediction preprocessing. Does not call prepare_mesh."""
    import sys

    import numpy as np
    import torch

    source = Path(ToothInstanceNetConfig.from_environment().source_root or "")
    if not source.is_dir():
        raise RuntimeError("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE is not a directory.")
    resolved = str(source.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    import teethland.data.transforms as transforms
    from teethland.data.datasets import TeethSegDataset

    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    staged = mesh_path
    if arch not in staged.stem.lower():
        staged = mesh_path.with_name(f"{arch}-{mesh_path.name}")
        if not staged.exists():
            staged.write_bytes(mesh_path.read_bytes())
    dataset = TeethSegDataset(
        stage="predict",
        root=staged.parent,
        files=[Path(staged.name)],
        norm=True,
        clean=True,
        transform=transforms.Compose(
            transforms.UniformDensityDownsample(0.025),
            transforms.XYZAsFeatures(),
            transforms.NormalAsFeatures(),
            transforms.ToTensor(),
        ),
    )
    item = dataset[0]
    item["arch"] = arch
    item["seed"] = seed
    return item


def _faces_match_server_mesh(mesh_path: Path, official_faces: Any) -> bool:
    import numpy as np
    import trimesh

    loaded = trimesh.load(mesh_path, force="mesh", process=False)
    server_faces = np.asarray(loaded.faces, dtype=np.int64)
    official = np.asarray(official_faces, dtype=np.int64)
    return server_faces.shape == official.shape and bool(np.array_equal(server_faces, official))


def _instances_from_vertex_labels(
    *,
    instance_labels: Any,
    class_labels: Any,
    class_confidences: Any,
    faces: Any,
) -> list[dict[str, Any]]:
    """Project vertex labels onto faces only when all three vertices agree."""
    import numpy as np

    labels = np.asarray(instance_labels, dtype=np.int64)
    triangles = np.asarray(faces, dtype=np.int64)
    classes = np.asarray(class_labels, dtype=np.int64)
    confidences = np.asarray(class_confidences, dtype=np.float64)
    rows = []
    for instance_id in sorted(int(value) for value in np.unique(labels) if int(value) >= 0):
        owned = np.flatnonzero(labels == instance_id)
        if len(owned) == 0:
            continue
        face_mask = np.all(np.isin(triangles, owned), axis=1)
        face_indices = [int(index) for index in np.flatnonzero(face_mask).tolist()]
        if not face_indices:
            continue
        model_class = None
        if 0 <= instance_id < len(classes):
            candidate = int(classes[instance_id])
            if 0 <= candidate < 7:
                model_class = candidate
        confidence = None
        available = False
        if 0 <= instance_id < len(confidences):
            score = float(confidences[instance_id])
            if np.isfinite(score) and 0.0 <= score <= 1.0:
                confidence = score
                available = True
        rows.append(
            {
                "instance_id": f"inst-{len(rows)}",
                "face_indices": face_indices,
                "raw_model_class": model_class,
                "model_class_is_fdi": False,
                "fdi": None,
                "confidence": confidence,
                "confidence_available": available,
                "confidence_label": "model_confidence" if available else "NOT_AVAILABLE",
            }
        )
    return rows


def _forward_official(mesh_path: Path, *, arch: str, seed: int) -> dict[str, Any]:
    """DentalNet forward on official dataset tensors. No FDI mapping."""
    import numpy as np
    import torch
    from time import perf_counter

    from adapters.toothinstancenet.adapter import ToothInstanceNetAdapter

    config = ToothInstanceNetConfig.from_environment()
    if config.device == "auto":
        config = ToothInstanceNetConfig(
            checkpoint_path=config.checkpoint_path,
            source_root=config.source_root,
            device="cuda",
        )
    adapter = ToothInstanceNetAdapter(config)
    item = _official_dataset_item(mesh_path, arch=arch, seed=seed)
    if not _faces_match_server_mesh(mesh_path, item["triangles"].detach().cpu().numpy()):
        raise RuntimeError(
            "Official dataset triangles do not match the trimesh faces of the prepared file. "
            "Face indices were not remapped."
        )
    model = adapter._build_model()
    torch_module, point_tensor, _ = adapter._import_upstream()
    device = adapter._device(torch_module)
    if device.type != "cuda":
        raise RuntimeError("EXTERNAL_CUDA requires a CUDA device. CPU forward was not run.")
    torch_module.cuda.reset_peak_memory_stats(device)
    points = item["points"].to(device)
    features = item["features"].to(device)
    downsample = item["ud_downsample_idxs"].to(device)
    batch = point_tensor(
        coordinates=points,
        features=features,
        batch_counts=torch_module.tensor([len(points)], device=device, dtype=torch_module.int64),
    )
    batch.cache["cp_downsample_idxs"] = downsample
    batch.cache["ts_downsample_idxs"] = downsample
    started = perf_counter()
    with torch_module.inference_mode():
        sampled = batch[batch.cache["cp_downsample_idxs"]]
        _, (spatial_embeds, seeds, learned_features) = model.instance_model(sampled)
        offsets = spatial_embeds.new_tensor(features=spatial_embeds.F[:, :3])
        sigmas = spatial_embeds.new_tensor(features=spatial_embeds.F[:, 3:])
        clusters = adapter._learned_region_cluster(offsets, sigmas, seeds)
        if arch != "lower":
            clusters._coordinates[clusters.batch_counts[0] :, 0] *= -1
        _, class_scores = model.identify_model(learned_features, clusters)
        full = point_tensor(
            coordinates=points,
            features=features,
            batch_counts=torch_module.tensor([len(points)], device=device, dtype=torch_module.int64),
        )
        interpolated = clusters.interpolate(full)
        instance_labels = interpolated.F.detach().cpu().numpy().astype(np.int64)
        class_labels = torch_module.argmax(class_scores.F, dim=-1).detach().cpu().numpy().astype(np.int64)
        class_confidences = (
            torch_module.softmax(class_scores.F, dim=-1).max(dim=-1).values.detach().cpu().numpy()
        )
    duration_ms = (perf_counter() - started) * 1000
    instances = _instances_from_vertex_labels(
        instance_labels=instance_labels,
        class_labels=class_labels,
        class_confidences=class_confidences,
        faces=item["triangles"].detach().cpu().numpy(),
    )
    return {
        "instances": instances,
        "inference_duration_ms": duration_ms,
        "peak_gpu_memory_bytes": int(torch_module.cuda.max_memory_allocated(device)),
        "point_count": int(points.shape[0]),
        "downsample_count": int(downsample.shape[0]),
        "upper_coordinate_flip_applied": arch != "lower",
        "fdi_assigned": False,
    }


def run_external_inference(
    *,
    prepared_mesh: Path,
    case_id: str,
    arch: str,
    output_dir: Path,
    seed: int | None,
    execute: bool,
    reproducibility_claimed: bool = True,
) -> dict[str, Any]:
    """Prepare or execute one external run. Execution never relabels itself as local."""
    if not execute:
        return {
            **external_run_status(),
            "executed": False,
            "message": "Pass --execute on the qualified CUDA host. This process did not infer.",
        }
    blockers: list[str] = []
    if seed is None and reproducibility_claimed:
        blockers.append("reproducibility_seed_missing")
    if arch not in {"upper", "lower"}:
        blockers.append("arch_invalid")
    if not prepared_mesh.is_file():
        blockers.append("prepared_mesh_missing")
    config = None
    try:
        config = ToothInstanceNetConfig.from_environment()
        config.verify_checkpoint()
    except Exception as exc:  # noqa: BLE001 - preflight must stay explicit
        blockers.append(f"checkpoint_unavailable:{type(exc).__name__}")
    runtime = _measure_runtime()
    for field in EXTERNAL_RUNTIME_FIELDS:
        if not runtime.get(field):
            blockers.append(f"{field}_missing")
    if blockers:
        return write_blocked_bundle(
            output_dir,
            blockers=blockers,
            detail={"prepared_mesh": str(prepared_mesh), "case_id": case_id, "arch": arch},
        )
    assert config is not None
    assert seed is not None
    try:
        produced = _forward_official(prepared_mesh, arch=arch, seed=seed)
    except Exception as exc:  # noqa: BLE001 - a failed external run must not invent output
        return write_blocked_bundle(
            output_dir,
            blockers=[f"inference_failed:{type(exc).__name__}"],
            detail={"message": str(exc), "prepared_mesh": str(prepared_mesh)},
        )
    prepared_sha = sha256_file(prepared_mesh)
    checkpoint_sha = sha256_file(config.checkpoint_path)
    payload = build_external_import_payload(
        run_id=f"external-{case_id}-{arch}",
        case_id=case_id,
        arch=arch,
        prepared_input_sha256=prepared_sha,
        checkpoint_sha256=checkpoint_sha,
        runtime=runtime,
        rng_seed=seed,
        reproducibility_claimed=reproducibility_claimed,
        raw_instances=produced["instances"],
        inference_duration_ms=produced["inference_duration_ms"],
        peak_gpu_memory_bytes=produced["peak_gpu_memory_bytes"],
        model_version=config.model_version,
    )
    validation = {
        "server_seal": "NOT_RUN",
        "sealable_candidate": bool(produced["instances"]),
        "face_assignment": FACE_ASSIGNMENT,
        "repaired": False,
        "point_count": produced["point_count"],
        "downsample_count": produced["downsample_count"],
        "instance_count": len(produced["instances"]),
        "clinical_validation": False,
    }
    if not produced["instances"]:
        validation["sealable_candidate"] = False
        validation["blockers"] = ["raw_output_missing"]
    preprocessing = {
        "implementation": OFFICIAL_PREPROCESSING,
        "not_used": FORBIDDEN_PREPROCESSING_SUBSTITUTE,
        "pipeline": list(PREDICTION_PREPROCESSING_PIPELINE),
        "dataset_flags": {"norm": True, "clean": True, "with_color": False},
        "rng_seed": seed,
        "inference_determinism": INFERENCE_DETERMINISM,
        "upper_coordinate_flip_applied": produced["upper_coordinate_flip_applied"],
        "fdi_assigned": False,
    }
    model = model_configuration_record()
    model["checkpoint_sha256_observed"] = checkpoint_sha
    return write_completed_bundle(
        output_dir,
        payload=payload,
        runtime=runtime,
        preprocessing=preprocessing,
        model=model,
        validation=validation,
    )
