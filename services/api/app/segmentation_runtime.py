"""REAL_CASE segmentation runtime capability.

Reports whether the configured real backend can execute. Never selects
TEST_FIXTURE and never substitutes fixture geometry.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
from pathlib import Path
from typing import Any

from app.processing_modes import selected_backend

TOOTHINSTANCENET_CHECKPOINT_SHA256 = (
    "100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803"
)
TOOTHINSTANCENET_SOURCE_REVISION = "424252e3d94a1565c8c2090eb5bb456b76386b93"
KNOWN_CHECKPOINT_CACHE = (
    Path.home()
    / ".cache/alignerstudio-research/toothinstancenet/checkpoints/instseg_full.ckpt"
)

# Documented acceptance runtime. CPU inference is not supported: pointops is a
# CUDA extension and the acceptance runner refuses a host without CUDA.
TOOTHINSTANCENET_REQUIREMENTS = (
    "NVIDIA driver that nvidia-smi can talk to",
    "CUDA toolkit/runtime compatible with the compiled pointops extension",
    "PyTorch with CUDA (validated research image: PyTorch 2.10.0+cu128 on CUDA 12.8; "
    "upstream 3dteethland docs also cite PyTorch 2.3.0/CUDA 12.1)",
    "Python package pointops (CUDA extension)",
    f"checkpoint instseg_full.ckpt SHA-256 {TOOTHINSTANCENET_CHECKPOINT_SHA256}",
    f"source revision {TOOTHINSTANCENET_SOURCE_REVISION}",
    "ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet",
    "ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT and ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE",
)


def _module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _nvidia_driver_visible() -> bool:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "-L"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and bool(completed.stdout.strip())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_uploaded_mesh(path: Path, *, arch: str, source_sha256: str) -> dict[str, Any]:
    """Record source identity. Does not write the file or build a derived mesh."""
    before = source_sha256
    record: dict[str, Any] = {
        "arch": arch,
        "source_mesh_path": str(path),
        "source_mesh_sha256": before,
        "source_bytes_modified": False,
        "derived_working_copy": False,
        "vertex_count": None,
        "face_count": None,
        "watertight": None,
        "coordinate_system": "source_file_coordinates",
        "units": "unverified",
        "format": path.suffix.lower().lstrip(".") or "unknown",
    }
    try:
        import trimesh

        mesh = trimesh.load(path, force="mesh", process=False)
        record["vertex_count"] = int(len(mesh.vertices))
        record["face_count"] = int(len(mesh.faces))
        record["watertight"] = bool(mesh.is_watertight)
    except Exception as error:  # noqa: BLE001 - inspection must not replace the failure
        record["mesh_read_error"] = str(error)
    after = _sha256_file(path) if path.is_file() else before
    record["source_mesh_sha256_after_inspect"] = after
    record["source_bytes_modified"] = after != before
    return record


def _onnx_assessment() -> dict[str, Any]:
    model = os.environ.get("ALIGNERSTUDIO_SEGMENTATION_MODEL", "").strip()
    contract = os.environ.get("ALIGNERSTUDIO_SEGMENTATION_CONTRACT", "").strip()
    model_path = Path(model) if model else None
    contract_path = Path(contract) if contract else None
    model_exists = bool(model_path and model_path.is_file())
    contract_exists = bool(contract_path and contract_path.is_file())
    onnxruntime_present = _module_present("onnxruntime")
    reason = (
        "ONNX is the configured REAL_CASE backend, but it cannot segment this upload. "
        "The adapter is a MeshSegNet face-feature contract (one input tensor of "
        "per-face features, CPUExecutionProvider only) and ships with no weights. "
        "It is not a ToothInstanceNet substitute. "
        "Set ALIGNERSTUDIO_SEGMENTATION_MODEL and ALIGNERSTUDIO_SEGMENTATION_CONTRACT "
        "to a legally cleared model whose SHA-256 matches the contract. "
        "No fixture fallback is used."
    )
    ready = model_exists and contract_exists and onnxruntime_present
    return {
        "backend": "onnx",
        "model_configured": bool(model and contract),
        "model_file_present": model_exists,
        "contract_file_present": contract_exists,
        "onnxruntime_present": onnxruntime_present,
        "providers": ["CPUExecutionProvider"],
        "gpu_required": False,
        "cpu_inference_supported": True,
        "can_segment_without_external_weights": False,
        "capability": "ready" if ready else "blocked_by_environment",
        "blocker": None if ready else reason,
    }


def _toothinstancenet_assessment() -> dict[str, Any]:
    checkpoint = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT", "").strip()
    source = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE", "").strip()
    checkpoint_path = Path(checkpoint) if checkpoint else None
    torch_present = _module_present("torch")
    pointops_present = _module_present("pointops")
    driver_visible = _nvidia_driver_visible()
    missing: list[str] = []
    if not checkpoint or checkpoint_path is None or not checkpoint_path.is_file():
        missing.append("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT")
    if not source or not Path(source).is_dir():
        missing.append("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE")
    if not torch_present:
        missing.append("torch")
    if not pointops_present:
        missing.append("pointops")
    if not driver_visible:
        missing.append("NVIDIA driver (nvidia-smi)")
    cache_note = ""
    if KNOWN_CHECKPOINT_CACHE.is_file() and not checkpoint:
        cache_note = (
            f" A checkpoint file is on disk at {KNOWN_CHECKPOINT_CACHE} but is not "
            "selected, because the checkpoint environment variable is unset."
        )
    blocker = None
    if missing:
        blocker = (
            "ToothInstanceNet REAL_CASE inference is blocked by environment. "
            f"Missing: {', '.join(missing)}. "
            "CPU inference is not supported (pointops is a CUDA extension). "
            "Required: "
            + "; ".join(TOOTHINSTANCENET_REQUIREMENTS)
            + "."
            + cache_note
            + " No fixture substitution."
        )
    return {
        "backend": "toothinstancenet",
        "checkpoint_configured": bool(checkpoint_path and checkpoint_path.is_file()),
        "source_configured": bool(source and Path(source).is_dir()),
        "known_checkpoint_cache_present": KNOWN_CHECKPOINT_CACHE.is_file(),
        "torch_present": torch_present,
        "pointops_present": pointops_present,
        "nvidia_driver_visible": driver_visible,
        "cpu_inference_supported": False,
        "gpu_required": True,
        "requirements": list(TOOTHINSTANCENET_REQUIREMENTS),
        "capability": "blocked_by_environment" if missing else "ready",
        "blocker": blocker,
    }


def assess_segmentation_runtime() -> dict[str, Any]:
    """Describe the configured real backend. Fixture mode is never implied."""
    backend = selected_backend()
    if backend == "toothinstancenet_fixture":
        detail = _toothinstancenet_assessment()
        detail["capability"] = "blocked_by_environment"
        detail["blocker"] = (
            "toothinstancenet_fixture is test-only and is not a REAL_CASE backend. "
            "No fixture substitution."
        )
        return {
            "processing_mode": "real_case",
            "backend": backend,
            "fixture_selected": False,
            "capability": "blocked_by_environment",
            "blocker": detail["blocker"],
            "recoverable": True,
            "detail": detail,
        }
    if backend == "toothinstancenet":
        detail = _toothinstancenet_assessment()
    elif backend == "onnx":
        detail = _onnx_assessment()
    else:
        detail = {
            "backend": backend,
            "capability": "blocked_by_environment",
            "blocker": (
                f"Unknown segmentation backend '{backend}'. "
                "REAL_CASE accepts onnx or toothinstancenet. No fixture substitution."
            ),
        }
    capability = detail.get("capability", "blocked_by_environment")
    return {
        "processing_mode": "real_case",
        "backend": backend,
        "fixture_selected": False,
        "capability": capability,
        "blocker": detail.get("blocker"),
        "recoverable": capability != "ready",
        "detail": detail,
    }
