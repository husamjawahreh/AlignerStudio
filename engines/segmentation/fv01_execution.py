"""FV-01.1 execution report.

Measures runtime readiness and, when the checkpoint can be read, the tensor
contract. It does not run ToothInstanceNet, does not select a fixture, and
does not invent an ONNX or CPU model.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import platform
import resource
import shutil
import subprocess
from enum import StrEnum
from pathlib import Path
from time import perf_counter
from typing import Any

from adapters.toothinstancenet.contract import ToothInstanceNetConfig
from engines.segmentation.fv01_checkpoint_contract import extract_checkpoint_contract
from engines.segmentation.fv01_probe import (
    PINNED_CHECKPOINT_SHA256,
    _checkpoint_facts,
    _cpu_model,
    _gpu_query,
    _mem_total_bytes,
    _module_present,
    _onnx_facts,
    _torch_facts,
)

DISCOVERED_SOURCE = Path.home() / ".cache/alignerstudio-research/toothinstancenet/source"
DISCOVERED_CHECKPOINT = (
    Path.home() / ".cache/alignerstudio-research/toothinstancenet/checkpoints/instseg_full.ckpt"
)
PINNED_SOURCE_REVISION = ToothInstanceNetConfig.source_revision

EXIT_CODES = {
    "INFERENCE_SUCCEEDED": 0,
    "READY": 0,
    "DRIVER_UNAVAILABLE": 2,
    "GPU_UNAVAILABLE": 3,
    "CUDA_UNAVAILABLE": 4,
    "PYTORCH_UNAVAILABLE": 5,
    "POINTOPS_UNAVAILABLE": 6,
    "ONNX_UNAVAILABLE": 7,
    "MODEL_MISSING": 8,
    "MODEL_LOAD_FAILED": 9,
    "MODEL_CONTRACT_UNKNOWN": 10,
    "INPUT_INVALID": 11,
    "INFERENCE_FAILED": 12,
    "ONNX_BACKEND_NOT_READY": 13,
}


class ExecutionState(StrEnum):
    READY = "READY"
    GPU_UNAVAILABLE = "GPU_UNAVAILABLE"
    DRIVER_UNAVAILABLE = "DRIVER_UNAVAILABLE"
    CUDA_UNAVAILABLE = "CUDA_UNAVAILABLE"
    PYTORCH_UNAVAILABLE = "PYTORCH_UNAVAILABLE"
    POINTOPS_UNAVAILABLE = "POINTOPS_UNAVAILABLE"
    ONNX_UNAVAILABLE = "ONNX_UNAVAILABLE"
    ONNX_BACKEND_NOT_READY = "ONNX_BACKEND_NOT_READY"
    MODEL_MISSING = "MODEL_MISSING"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    MODEL_CONTRACT_UNKNOWN = "MODEL_CONTRACT_UNKNOWN"
    INPUT_INVALID = "INPUT_INVALID"
    INFERENCE_FAILED = "INFERENCE_FAILED"
    INFERENCE_SUCCEEDED = "INFERENCE_SUCCEEDED"


def _source_revision(source: Path | None) -> str | None:
    if source is None or not source.is_dir():
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _cpu_fallback(source: Path | None) -> dict[str, Any]:
    setup = None if source is None else source / "setup.py"
    if setup is None or not setup.is_file():
        return {
            "implemented": False,
            "meaningful_on_cpu": None,
            "decision": "NOT_MEASURED",
            "reason": (
                "The pinned source checkout is not available, so the pointops build was not read."
            ),
        }
    text = setup.read_text(encoding="utf-8", errors="replace")
    cuda_extension = "CUDAExtension" in text
    cpp_extension = "CppExtension" in text
    cuda_sources = text.count(".cu")
    meaningful = False if cuda_extension and not cpp_extension else None
    return {
        "implemented": False,
        "meaningful_on_cpu": meaningful,
        "decision": "RULED_OUT" if meaningful is False else "NOT_MEASURED",
        "cuda_extension": cuda_extension,
        "cpp_extension": cpp_extension,
        "cuda_source_mentions": cuda_sources,
        "setup_path": str(setup),
        "reason": (
            "pointops is built only as a CUDAExtension. The pinned setup.py has "
            "no CppExtension. A CPU forward of the network is not available. "
            "No CPU fallback was added."
            if meaningful is False
            else "The pointops build type could not be classified."
        ),
    }


def _config_yaml_note(source: Path | None) -> dict[str, Any]:
    path = None if source is None else source / "teethland/config/config.yaml"
    if path is None or not path.is_file():
        return {"present": False, "path": None if path is None else str(path)}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "present": True,
        "path": str(path),
        "distinguish_left_right_true": "distinguish_left_right: true" in text,
        "m3_as_m2_false": "m3_as_m2: False" in text,
        "matches_seven_class_formula": False,
        "reason": (
            "This yaml sets distinguish_left_right true and m3_as_m2 false. "
            "TeethInstSegDataModule.num_classes would not return 7 for that pair. "
            "The yaml is not the stored config of instseg_full.ckpt."
        ),
    }


def _onnx_backend(onnx_runtime: dict[str, Any]) -> dict[str, Any]:
    configured = os.environ.get("ALIGNERSTUDIO_SEGMENTATION_MODEL", "").strip()
    contract = os.environ.get("ALIGNERSTUDIO_SEGMENTATION_CONTRACT", "").strip()
    model_path = Path(configured) if configured else None
    model_exists = bool(model_path and model_path.is_file())
    artifact_present = model_exists and model_path.suffix.lower() == ".onnx"
    runtime_present = bool(onnx_runtime.get("available"))
    states: list[str] = []
    if not runtime_present:
        states.append(ExecutionState.ONNX_UNAVAILABLE.value)
    if not artifact_present:
        states.append(ExecutionState.ONNX_BACKEND_NOT_READY.value)
    return {
        "states": states,
        "runtime_present": runtime_present,
        "runtime_version": onnx_runtime.get("version"),
        "model_env_set": bool(configured),
        "model_file_present": model_exists,
        "onnx_artifact_present": artifact_present,
        "contract_env_set": bool(contract),
        "generated_this_phase": False,
        "is_toothinstancenet_substitute": False,
        "reason": (
            "No ToothInstanceNet ONNX artifact is configured, and ONNX Runtime "
            "is not installed. The default onnx backend is not a measured fallback. "
            "An ONNX model was not exported."
        ),
    }


def _pointops_facts() -> dict[str, Any]:
    present = _module_present("pointops")
    version = None
    if present:
        import pointops

        version = getattr(pointops, "__version__", None)
        spec = importlib.util.find_spec("pointops")
        location = None if spec is None else spec.origin
    else:
        location = None
    return {"available": present, "version": version, "location": location}


def classify_execution(facts: dict[str, Any]) -> dict[str, Any]:
    """Choose a primary state without collapsing the other applicable failures."""
    applicable: list[str] = []
    driver_visible = bool(facts.get("driver_visible"))
    nvidia_present = bool(facts.get("nvidia_smi_present"))
    torch_available = bool(facts.get("torch_available"))
    if facts.get("inference_succeeded"):
        applicable.append(ExecutionState.INFERENCE_SUCCEEDED.value)
    elif facts.get("inference_failed"):
        applicable.append(ExecutionState.INFERENCE_FAILED.value)
    if nvidia_present and not driver_visible:
        applicable.append(ExecutionState.DRIVER_UNAVAILABLE.value)
    elif not driver_visible:
        applicable.append(ExecutionState.GPU_UNAVAILABLE.value)
    if not torch_available:
        applicable.append(ExecutionState.PYTORCH_UNAVAILABLE.value)
    elif not facts.get("cuda_available"):
        applicable.append(ExecutionState.CUDA_UNAVAILABLE.value)
    if not facts.get("pointops_available"):
        applicable.append(ExecutionState.POINTOPS_UNAVAILABLE.value)
    if not facts.get("checkpoint_present"):
        applicable.append(ExecutionState.MODEL_MISSING.value)
    elif facts.get("model_load_failed"):
        applicable.append(ExecutionState.MODEL_LOAD_FAILED.value)
    elif not facts.get("tensor_contract_rederived"):
        applicable.append(ExecutionState.MODEL_CONTRACT_UNKNOWN.value)
    for state in facts.get("onnx_states") or []:
        if state not in applicable:
            applicable.append(state)
    ready = (
        driver_visible
        and torch_available
        and facts.get("cuda_tensor_executed")
        and facts.get("pointops_available")
        and facts.get("checkpoint_present")
        and facts.get("checkpoint_hash_matches") is True
        and facts.get("tensor_contract_rederived")
        and facts.get("source_revision_matches") is True
        and not facts.get("inference_failed")
    )
    if facts.get("input_invalid"):
        applicable.append(ExecutionState.INPUT_INVALID.value)
        ready = False
    if ready and not facts.get("inference_succeeded"):
        applicable.append(ExecutionState.READY.value)
    if not applicable:
        applicable.append(ExecutionState.MODEL_CONTRACT_UNKNOWN.value)
    primary = applicable[0]
    return {
        "primary_state": primary,
        "applicable_states": applicable,
        "exit_code": EXIT_CODES.get(primary, 1),
        "ready": primary in {
            ExecutionState.READY.value,
            ExecutionState.INFERENCE_SUCCEEDED.value,
        },
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _execute_real_stl(
    *,
    stl_path: Path,
    checkpoint: Path,
    source: Path,
) -> dict[str, Any]:
    """Run the production ToothInstanceNet engine. Callers must already be READY."""
    from adapters.toothinstancenet.adapter import ToothInstanceNetAdapter
    from domain.tooth.identification import ArchType
    from engines.segmentation.toothinstancenet import ToothInstanceNetEngine

    config = ToothInstanceNetConfig(
        checkpoint_path=checkpoint,
        source_root=source,
        device="cuda",
    )
    engine = ToothInstanceNetEngine(ToothInstanceNetAdapter(config), arch=ArchType.UPPER)
    result = engine.segment(str(stl_path))
    labels = [
        tooth.semantic_label
        for tooth in result.identification.teeth
    ]
    confidences = [
        tooth.confidence.score if tooth.confidence_available else None
        for tooth in result.identification.teeth
    ]
    identities = [tooth.identity for tooth in result.identification.teeth]
    return {
        "attempted": True,
        "succeeded": True,
        "input_sha256": _sha256_file(stl_path),
        "arch": "upper",
        "model_sha256": config.checkpoint_sha256,
        "model_version": config.model_version,
        "backend": "toothinstancenet",
        "algorithm_version": config.model_version,
        "instance_count": len(result.segmentation.instances),
        "class_labels": labels,
        "confidences": confidences,
        "identities": [None if item is None else str(item) for item in identities],
        "fdi_authoritative": result.diagnostics.fdi_authoritative,
        "clinical_accuracy_claim": result.diagnostics.clinical_accuracy_claim,
        "planning_modes": [tooth.planning_mode for tooth in result.identification.teeth],
        "fixture": result.identification.fixture,
        "timings_ms": result.timings_ms,
        "status": result.status,
    }


def run_fv01_execution(
    *,
    hash_checkpoint: bool = True,
    extract_contract: bool = True,
    checkpoint_path: Path | None = None,
    attempt_inference: bool = False,
    stl_path: Path | None = None,
) -> dict[str, Any]:
    """Build the machine-readable FV-01.1 report. Does not change the environment."""
    started = perf_counter()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    configured = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT", "").strip()
    source_env = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE", "").strip()
    selected = Path(checkpoint_path) if checkpoint_path is not None else (
        Path(configured) if configured else None
    )
    discovered = selected if selected is not None else (
        DISCOVERED_CHECKPOINT if DISCOVERED_CHECKPOINT.is_file() else None
    )
    source = Path(source_env) if source_env else (
        DISCOVERED_SOURCE if DISCOVERED_SOURCE.is_dir() else None
    )
    gpu = _gpu_query()
    torch_facts = _torch_facts()
    pointops = _pointops_facts()
    onnx_runtime = _onnx_facts()
    checkpoint = _checkpoint_facts(discovered, hash_file=hash_checkpoint)
    contract_started = perf_counter()
    if extract_contract and checkpoint["present"] and discovered is not None:
        contract = extract_checkpoint_contract(discovered)
    elif not checkpoint["present"]:
        contract = {
            "state": ExecutionState.MODEL_MISSING.value,
            "tensor_contract_rederived": False,
            "reason": "No checkpoint file was available to load.",
        }
    else:
        contract = {
            "state": ExecutionState.MODEL_CONTRACT_UNKNOWN.value,
            "tensor_contract_rederived": False,
            "reason": "Contract extraction was not requested.",
        }
    contract_ms = (perf_counter() - contract_started) * 1000
    revision = _source_revision(source)
    cpu = _cpu_fallback(source)
    onnx = _onnx_backend(onnx_runtime)
    driver_visible = bool(gpu["nvidia_driver_visible"])
    base_facts = {
        "driver_visible": driver_visible,
        "nvidia_smi_present": gpu["nvidia_smi_present"],
        "torch_available": torch_facts["available"],
        "cuda_available": torch_facts["cuda_available"],
        "cuda_tensor_executed": torch_facts["cuda_tensor_executed"],
        "pointops_available": pointops["available"],
        "checkpoint_present": checkpoint["present"],
        "checkpoint_hash_matches": checkpoint["matches_pinned_digest"],
        "model_load_failed": contract.get("state") == ExecutionState.MODEL_LOAD_FAILED.value,
        "tensor_contract_rederived": bool(contract.get("tensor_contract_rederived")),
        "source_revision_matches": revision == PINNED_SOURCE_REVISION,
        "onnx_states": onnx["states"],
        "input_invalid": False,
        "inference_failed": False,
        "inference_succeeded": False,
    }
    preflight = classify_execution(base_facts)
    inference: dict[str, Any] = {
        "attempted": False,
        "succeeded": False,
        "reason": "Inference was not requested.",
    }
    if attempt_inference:
        stl = None if stl_path is None else Path(stl_path)
        if stl is None or not stl.is_file() or stl.suffix.lower() != ".stl":
            base_facts["input_invalid"] = True
            inference = {
                "attempted": False,
                "succeeded": False,
                "reason": "A real .stl path is required before inference can start.",
            }
        elif not preflight["ready"]:
            inference = {
                "attempted": False,
                "succeeded": False,
                "reason": (
                    "Inference was requested and refused. The runtime is not READY. "
                    f"Primary state: {preflight['primary_state']}."
                ),
            }
        elif discovered is None or source is None:
            base_facts["input_invalid"] = True
            inference = {
                "attempted": False,
                "succeeded": False,
                "reason": "Checkpoint or source path disappeared before inference.",
            }
        else:
            try:
                inference = _execute_real_stl(stl_path=stl, checkpoint=discovered, source=source)
                base_facts["inference_succeeded"] = True
            except Exception as exc:  # noqa: BLE001 - report the failure, do not substitute a fixture
                base_facts["inference_failed"] = True
                inference = {
                    "attempted": True,
                    "succeeded": False,
                    "reason": str(exc),
                }
    classified = classify_execution(base_facts)
    elapsed_ms = (perf_counter() - started) * 1000
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    timings = inference.get("timings_ms") or {}
    return {
        "primary_state": classified["primary_state"],
        "applicable_states": classified["applicable_states"],
        "exit_code": classified["exit_code"],
        "ready": classified["ready"],
        "fixture_selected": False,
        "clinical_accuracy_claim": False,
        "clinical_accuracy": "NOT_ESTABLISHED",
        "output_class": "ENGINEERING_OUTPUT",
        "architecture_recommendation": "B",
        "os": platform.platform(),
        "cpu": _cpu_model(),
        "ram_bytes": _mem_total_bytes(),
        "python": platform.python_version(),
        "pytorch": torch_facts,
        "cuda": {
            **gpu,
            "torch_cuda_available": torch_facts["cuda_available"],
            "torch_cuda_version": torch_facts["cuda_version"],
            "cuda_device": gpu.get("gpu_name"),
            "cuda_tensor_executed": torch_facts["cuda_tensor_executed"],
        },
        "driver": {
            "nvidia_smi_present": gpu["nvidia_smi_present"],
            "visible": driver_visible,
            "returncode": gpu["nvidia_smi_returncode"],
            "message": gpu["nvidia_smi_stdout"] or gpu["nvidia_smi_stderr"],
        },
        "pointops": pointops,
        "onnx": onnx,
        "backend_selected": os.environ.get(
            "ALIGNERSTUDIO_SEGMENTATION_BACKEND", "onnx"
        ).strip().lower(),
        "checkpoint": checkpoint,
        "pinned_checkpoint_sha256": PINNED_CHECKPOINT_SHA256,
        "source": {
            "path": None if source is None else str(source),
            "revision": revision,
            "pinned_revision": PINNED_SOURCE_REVISION,
            "matches_pin": revision == PINNED_SOURCE_REVISION,
            "env_set": bool(source_env),
        },
        "contract": contract,
        "config_yaml": _config_yaml_note(source),
        "cpu_fallback": cpu,
        "inference": inference,
        "performance": {
            "runner_ms": elapsed_ms,
            "contract_extraction_ms": contract_ms,
            "preprocess_ms": timings.get("preprocess_ms"),
            "inference_ms": timings.get("inference_ms"),
            "postprocess_ms": timings.get("postprocess_ms"),
            "persistence_ms": None,
            "peak_rss_kb_delta": rss_after - rss_before,
            "peak_gpu_memory_bytes": timings.get("peak_gpu_memory_bytes"),
            "reason": (
                "Inference completed through the production ToothInstanceNet engine."
                if inference.get("succeeded")
                else "Inference did not execute. The runner and contract extraction were measured."
            ),
        },
        "nvcc_present": shutil.which("nvcc") is not None,
    }
