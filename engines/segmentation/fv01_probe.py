"""Deterministic ToothInstanceNet environment probe.

Reports whether inference can execute. It does not download weights, does not
select a fixture backend, and does not treat a blocked host as a successful run.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import platform
import resource
import shutil
import subprocess
from pathlib import Path
from time import perf_counter
from typing import Any

from adapters.toothinstancenet.contract import ToothInstanceNetConfig
from domain.tooth.segmentation_proof import InferenceProofState

PINNED_CHECKPOINT_SHA256 = ToothInstanceNetConfig.checkpoint_sha256
DISCOVERED_CHECKPOINT = (
    Path.home() / ".cache/alignerstudio-research/toothinstancenet/checkpoints/instseg_full.ckpt"
)
DECLARED_CONTRACT = {
    "in_channels": ToothInstanceNetConfig.in_channels,
    "num_classes": ToothInstanceNetConfig.num_classes,
    "feature_layout": "sampled xyz concatenated with vertex normals",
    "preprocessing": {
        "zscore_std": ToothInstanceNetConfig.zscore_std,
        "uniform_density_voxel_size": ToothInstanceNetConfig.uniform_density_voxel_size,
        "pose_normalize": True,
    },
    "label_semantics": (
        "Code declares seven semantic classes. That declaration is not a tensor "
        "contract read from the checkpoint on this process unless "
        "tensor_contract_rederived is true."
    ),
    "left_right_in_class_set": False,
    "authoritative_fdi": False,
    "verified_against_loaded_weights": False,
}


def _module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _mem_total_bytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                kib = int(line.split()[1])
                return kib * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def _gpu_query() -> dict[str, Any]:
    listed = _run(["nvidia-smi", "-L"])
    visible = listed is not None and listed.returncode == 0 and bool(listed.stdout.strip())
    name = None
    if visible:
        queried = _run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
        if queried is not None and queried.returncode == 0:
            name = queried.stdout.strip().splitlines()[0].strip() or None
    return {
        "nvidia_smi_present": shutil.which("nvidia-smi") is not None,
        "nvidia_driver_visible": visible,
        "nvidia_smi_returncode": None if listed is None else listed.returncode,
        "nvidia_smi_stdout": "" if listed is None else listed.stdout.strip(),
        "nvidia_smi_stderr": "" if listed is None else listed.stderr.strip(),
        "gpu_name": name,
    }


def _torch_facts() -> dict[str, Any]:
    if not _module_present("torch"):
        return {
            "available": False,
            "version": None,
            "cuda_compiled": None,
            "cuda_available": False,
            "cuda_version": None,
            "cuda_tensor_executed": False,
        }
    import torch

    cuda_available = bool(torch.cuda.is_available())
    executed = False
    if cuda_available:
        tensor = torch.zeros(1, device="cuda")
        executed = int(tensor.numel()) == 1
        del tensor
        torch.cuda.empty_cache()
    return {
        "available": True,
        "version": torch.__version__,
        "cuda_compiled": torch.version.cuda,
        "cuda_available": cuda_available,
        "cuda_version": torch.version.cuda,
        "cuda_tensor_executed": executed,
    }


def _onnx_facts() -> dict[str, Any]:
    if not _module_present("onnxruntime"):
        return {"available": False, "version": None}
    import onnxruntime

    return {"available": True, "version": onnxruntime.__version__}


def _checkpoint_facts(path: Path | None, *, hash_file: bool) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {
            "path": None if path is None else str(path),
            "present": False,
            "sha256": None,
            "matches_pinned_digest": None,
            "bytes": None,
        }
    digest = _sha256_file(path) if hash_file else None
    return {
        "path": str(path),
        "present": True,
        "sha256": digest,
        "matches_pinned_digest": None if digest is None else digest == PINNED_CHECKPOINT_SHA256,
        "bytes": path.stat().st_size,
    }


def _contract_from_checkpoint(
    checkpoint: dict[str, Any], torch_facts: dict[str, Any]
) -> dict[str, Any]:
    """File identity is not a re-derived tensor contract."""
    if not checkpoint["present"] or not torch_facts["available"]:
        return {
            "state": InferenceProofState.MODEL_CONTRACT_UNKNOWN.value,
            "tensor_contract_rederived": False,
            "reason": (
                "The checkpoint state dict was not loaded. "
                "A pinned SHA-256 match, when present, identifies the file only. "
                "Class names were not used as the tensor contract."
            ),
        }
    return {
        "state": InferenceProofState.MODEL_CONTRACT_UNKNOWN.value,
        "tensor_contract_rederived": False,
        "reason": (
            "PyTorch is present, but this probe does not infer in_channels or "
            "num_classes from checkpoint key names."
        ),
    }


def _primary_state(
    *,
    gpu: dict[str, Any],
    torch_facts: dict[str, Any],
    checkpoint: dict[str, Any],
    source_configured: bool,
    pointops_present: bool,
    backend: str,
    contract_state: str,
    inference_executed: bool,
    inference_failed: bool,
) -> str:
    if inference_failed:
        return InferenceProofState.INFERENCE_FAILED.value
    if inference_executed and contract_state != InferenceProofState.MODEL_CONTRACT_UNKNOWN.value:
        return InferenceProofState.INFERENCE_READY.value
    if not gpu["nvidia_driver_visible"]:
        return InferenceProofState.GPU_UNAVAILABLE.value
    if torch_facts.get("available") and not torch_facts.get("cuda_available"):
        return InferenceProofState.GPU_UNAVAILABLE.value
    if not checkpoint["present"]:
        return InferenceProofState.MODEL_MISSING.value
    if not torch_facts["available"] or not pointops_present or not source_configured:
        return InferenceProofState.DEPENDENCY_MISSING.value
    if backend != "toothinstancenet":
        return InferenceProofState.BACKEND_UNAVAILABLE.value
    if contract_state == InferenceProofState.MODEL_CONTRACT_UNKNOWN.value:
        return InferenceProofState.MODEL_CONTRACT_UNKNOWN.value
    if (
        torch_facts.get("cuda_tensor_executed")
        and checkpoint.get("matches_pinned_digest") is True
        and source_configured
        and pointops_present
    ):
        return InferenceProofState.INFERENCE_READY.value
    return InferenceProofState.ENVIRONMENT_READY.value


def run_fv01_probe(
    *,
    hash_checkpoint: bool = True,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    """Inspect the host. Does not run ToothInstanceNet and does not change env."""
    started = perf_counter()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    backend = os.environ.get("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "onnx").strip().lower()
    configured = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT", "").strip()
    source = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE", "").strip()
    selected = Path(checkpoint_path) if checkpoint_path is not None else (
        Path(configured) if configured else None
    )
    discovered = selected if selected is not None else (
        DISCOVERED_CHECKPOINT if DISCOVERED_CHECKPOINT.is_file() else None
    )
    gpu = _gpu_query()
    torch_facts = _torch_facts()
    checkpoint = _checkpoint_facts(discovered, hash_file=hash_checkpoint)
    contract = _contract_from_checkpoint(checkpoint, torch_facts)
    pointops_present = _module_present("pointops")
    source_configured = bool(source and Path(source).is_dir())
    primary = _primary_state(
        gpu=gpu,
        torch_facts=torch_facts,
        checkpoint=checkpoint,
        source_configured=source_configured,
        pointops_present=pointops_present,
        backend=backend,
        contract_state=contract["state"],
        inference_executed=False,
        inference_failed=False,
    )
    applicable = {primary, contract["state"]}
    if not gpu["nvidia_driver_visible"] or not torch_facts.get("cuda_available"):
        applicable.add(InferenceProofState.GPU_UNAVAILABLE.value)
    if not checkpoint["present"]:
        applicable.add(InferenceProofState.MODEL_MISSING.value)
    if not torch_facts["available"] or not pointops_present or not source_configured:
        applicable.add(InferenceProofState.DEPENDENCY_MISSING.value)
    if backend != "toothinstancenet":
        applicable.add(InferenceProofState.BACKEND_UNAVAILABLE.value)
    elapsed_ms = (perf_counter() - started) * 1000
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "primary_state": primary,
        "applicable_states": sorted(applicable),
        "inference_can_execute": primary == InferenceProofState.INFERENCE_READY.value,
        "fixture_selected": False,
        "clinical_accuracy_claim": False,
        "output_class": "ENGINEERING_OUTPUT",
        "python_version": platform.python_version(),
        "os": platform.platform(),
        "cpu": _cpu_model(),
        "ram_bytes": _mem_total_bytes(),
        "backend_selected": backend,
        "backend_unavailable_reason": (
            None
            if backend == "toothinstancenet"
            else (
                f"ALIGNERSTUDIO_SEGMENTATION_BACKEND={backend}. "
                "ToothInstanceNet is not the selected real backend. "
                "The fixture backend is never selected by this probe."
            )
        ),
        "cuda": gpu,
        "torch": torch_facts,
        "pointops_present": pointops_present,
        "onnxruntime": _onnx_facts(),
        "source_configured": source_configured,
        "checkpoint_env_set": bool(configured),
        "checkpoint": checkpoint,
        "pinned_checkpoint_sha256": PINNED_CHECKPOINT_SHA256,
        "expected_input": {
            "representation": "triangle mesh",
            "channels": DECLARED_CONTRACT["in_channels"],
            "channel_meaning": DECLARED_CONTRACT["feature_layout"],
            "declared_only": True,
        },
        "expected_output": {
            "representation": "per-vertex instance ids and per-cluster class scores",
            "declared_class_count": DECLARED_CONTRACT["num_classes"],
            "labels_are_unique_fdi": False,
            "arch_produced_by_model": False,
            "left_right_produced_by_model": False,
            "fdi_produced_by_model": False,
            "declared_only": True,
        },
        "contract": {
            **contract,
            "code_declared_contract": DECLARED_CONTRACT,
            "checkpoint_matches_pinned_digest": checkpoint["matches_pinned_digest"],
        },
        "performance": {
            "probe_ms": elapsed_ms,
            "preprocess_ms": None,
            "inference_ms": None,
            "postprocess_ms": None,
            "persistence_ms": None,
            "peak_rss_kb_delta": rss_after - rss_before,
            "peak_gpu_memory_bytes": None,
            "reason": "Inference did not execute. Only the probe was measured.",
        },
    }
