"""FV-03.1 segmentation runtime manifest, self-test, and evidence seal.

This module does not import PyTorch or pointops. A missing runtime is recorded
as null or unavailable. It does not run a forward pass and does not invent
instances, confidence, or clinical accuracy.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
from datetime import UTC, datetime
from typing import Any

from adapters.toothinstancenet.contract import ToothInstanceNetConfig
from domain.tooth.segmentation_review import manual_segmentation_contract
from engines.segmentation.runtime_readiness import (
    SOURCE_REVISION,
    UPSTREAM_CUDA,
    UPSTREAM_TORCH,
    VALIDATED_CUDA_IMAGE,
    VALIDATED_PYTHON,
    VALIDATED_TORCH,
)

MANIFEST_VERSION = "fv03.1-runtime-1"
EVIDENCE_VERSION = "fv03.1-evidence-1"
SELF_TEST_STATES = frozenset(
    {
        "ENVIRONMENT_UNAVAILABLE",
        "MODEL_UNAVAILABLE",
        "MODEL_CONTRACT_INVALID",
        "RUNTIME_INITIALIZATION_FAILED",
        "INPUT_CONTRACT_INVALID",
        "READY_FOR_INFERENCE",
    }
)
ENVIRONMENT_SELF_TEST_BLOCKERS = frozenset(
    {
        "DRIVER_UNAVAILABLE",
        "GPU_UNAVAILABLE",
        "PYTORCH_UNAVAILABLE",
        "CUDA_EXTENSION_UNAVAILABLE",
    }
)
QUALITY_MEASUREMENTS = (
    "dice",
    "iou",
    "surface_distance",
    "hausdorff_distance",
    "instance_count",
    "connected_component_statistics",
    "boundary_statistics",
    "invalid_output_count",
    "self_intersecting_output_count",
)
REQUIRED_MODEL_OUTPUTS = {
    "instance_head": "offsets_and_sigmas",
    "seed_head": "seed_logit",
    "identify_head": "seven_logits",
    "instance_ids": "learned_region_cluster",
    "fdi_encoded": False,
    "arch_encoded": False,
    "left_right_encoded": False,
}
PINNED_CHECKPOINT_FILENAME = "instseg_full.ckpt"
PINNED_CHECKPOINT_SHA256 = ToothInstanceNetConfig.checkpoint_sha256


class EvidenceImmutableError(RuntimeError):
    """A completed evidence bundle cannot be edited."""


def environment_specification() -> dict[str, Any]:
    """Pins for a separate TIN runtime. Not a dependency of the application process."""
    return {
        "spec_version": "fv03.1-environment-1",
        "applies_to": "toothinstancenet",
        "application_dependency": False,
        "python": VALIDATED_PYTHON,
        "pytorch": {
            "validated_pin": VALIDATED_TORCH,
            "upstream_pin": UPSTREAM_TORCH,
            "mandatory_for_application_startup": False,
        },
        "cuda": {
            "validated_image": VALIDATED_CUDA_IMAGE,
            "upstream_pin": UPSTREAM_CUDA,
            "mandatory_for_application_startup": False,
        },
        "pointops": {
            "requirement": "CUDAExtension",
            "cpp_extension": False,
            "cpu_forward": False,
        },
        "checkpoint": {
            "filename": PINNED_CHECKPOINT_FILENAME,
            "sha256": PINNED_CHECKPOINT_SHA256,
            "model_contract_version": ToothInstanceNetConfig.model_version,
            "source_revision": SOURCE_REVISION,
        },
        "required_input_channels": ToothInstanceNetConfig.in_channels,
        "required_model_outputs": REQUIRED_MODEL_OUTPUTS,
        "expected_self_test_when_pins_match": "READY_FOR_INFERENCE",
        "build_steps": [
            "Use a separate environment. Do not add these packages to the application process.",
            "Install Python 3.12.",
            "Install the validated PyTorch CUDA build, or the upstream pin recorded above.",
            "Install a CUDA toolkit that matches that build.",
            "Build pointops from the pinned source as a CUDAExtension. There is no CppExtension.",
            "Place instseg_full.ckpt on the checkpoint path and verify its SHA-256.",
        ],
    }


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _driver_version(visible: bool) -> str | None:
    if not visible or shutil.which("nvidia-smi") is None:
        return None
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip().splitlines()
    return value[0].strip() or None if value else None


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


def build_runtime_manifest(
    report: dict[str, Any],
    *,
    capability_state: str | None = None,
    probe_host: bool = True,
) -> dict[str, Any]:
    """Copy measured host facts. Missing GPU, driver, CUDA, and PyTorch stay null."""
    pytorch = report.get("pytorch") or {}
    cuda = report.get("cuda") or {}
    driver = report.get("driver") or {}
    pointops = report.get("pointops") or {}
    checkpoint = report.get("checkpoint") or {}
    contract = report.get("contract") or {}
    driver_visible = bool(driver.get("visible"))
    gpu_model = cuda.get("cuda_device") or cuda.get("gpu_name")
    if not driver_visible:
        gpu_model = None
    torch_available = bool(pytorch.get("available"))
    cuda_version = pytorch.get("cuda_version") if torch_available else None
    if cuda_version is None and probe_host:
        cuda_version = _nvcc_version()
    filename = None
    checkpoint_path = checkpoint.get("path")
    if checkpoint.get("present") and isinstance(checkpoint_path, str) and checkpoint_path:
        filename = checkpoint_path.rsplit("/", 1)[-1] or None
    observed_channels = None
    point_input = contract.get("input") or {}
    if isinstance(point_input, dict) and point_input.get("in_channels") is not None:
        observed_channels = point_input.get("in_channels")
    return {
        "manifest_version": MANIFEST_VERSION,
        "python_version": report.get("python") or platform.python_version(),
        "os": report.get("os") or platform.platform(),
        "platform": platform.platform(),
        "cpu": report.get("cpu"),
        "ram_bytes": report.get("ram_bytes"),
        "gpu_vendor": "NVIDIA" if driver_visible and gpu_model else None,
        "gpu_model": gpu_model if driver_visible else None,
        "driver_version": _driver_version(driver_visible) if probe_host else None,
        "cuda_version": cuda_version,
        "pytorch_version": pytorch.get("version") if torch_available else None,
        "pytorch_available": torch_available,
        "cuda_extension_available": bool(pointops.get("available")),
        "pointops_available": bool(pointops.get("available")),
        "pointops_version": pointops.get("version") if pointops.get("available") else None,
        "backend_package_versions": {
            "trimesh": _package_version("trimesh"),
            "numpy": _package_version("numpy"),
            "torch": _package_version("torch"),
            "pointops": pointops.get("version") if pointops.get("available") else None,
        },
        "checkpoint_filename": filename,
        "checkpoint_sha256": checkpoint.get("sha256"),
        "checkpoint_present": bool(checkpoint.get("present")),
        "model_contract_version": ToothInstanceNetConfig.model_version,
        "required_input_channels": ToothInstanceNetConfig.in_channels,
        "observed_input_channels": observed_channels,
        "required_model_outputs": REQUIRED_MODEL_OUTPUTS,
        "observed_contract_state": contract.get("state"),
        "runtime_capability_state": capability_state or report.get("primary_state"),
    }


def classify_self_test(
    capability: dict[str, Any],
    *,
    init_error: str | None = None,
    input_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify readiness. This does not execute the network."""
    applicable = [str(item) for item in capability.get("applicable_states") or []]
    primary = str(capability.get("capability_state") or "")
    environment = [item for item in applicable if item in ENVIRONMENT_SELF_TEST_BLOCKERS]
    if primary in ENVIRONMENT_SELF_TEST_BLOCKERS and primary not in environment:
        environment.insert(0, primary)
    present = bool(capability.get("checkpoint_present"))
    hash_matches = capability.get("checkpoint_hash_matches")
    contract_state = capability.get("checkpoint_contract_state")
    contract_ok = contract_state == "TENSOR_CONTRACT_ESTABLISHED" and hash_matches is True
    if environment:
        state = "ENVIRONMENT_UNAVAILABLE"
    elif (
        not present
        or hash_matches is False
        or primary == "MODEL_ARTIFACT_UNAVAILABLE"
    ):
        state = "MODEL_UNAVAILABLE"
    elif not contract_ok or primary == "MODEL_CONTRACT_UNAVAILABLE":
        state = "MODEL_CONTRACT_INVALID"
    elif init_error or not capability.get("executable"):
        state = "RUNTIME_INITIALIZATION_FAILED"
    elif input_gate is not None and not input_gate.get("accepted"):
        state = "INPUT_CONTRACT_INVALID"
    else:
        state = "READY_FOR_INFERENCE"
    return {
        "state": state,
        "environment_blockers": environment,
        "checkpoint_present": present,
        "checkpoint_hash_matches": hash_matches,
        "contract_metadata_valid": contract_state == "TENSOR_CONTRACT_ESTABLISHED",
        "checkpoint_contract_state": contract_state,
        "init_error": init_error,
        "entered_inference": False,
        "real_inference": False,
        "clinically_verified": False,
    }


def quality_evaluation(
    *,
    ground_truth_present: bool,
    measurements: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record reference metrics only when reference truth was supplied."""
    empty = {name: None for name in QUALITY_MEASUREMENTS}
    if not ground_truth_present:
        return {
            "quality_evaluation": "NOT_AVAILABLE",
            "reason": "No reference segmentation is available. Scores were not computed.",
            "clinical_accuracy": "NOT_ESTABLISHED",
            **empty,
        }
    provided = measurements or {}
    recorded = {
        name: provided[name] if name in provided else None for name in QUALITY_MEASUREMENTS
    }
    return {
        "quality_evaluation": "RECORDED",
        "reason": "Reference truth was supplied. Only provided measurements are stored.",
        "clinical_accuracy": "NOT_ESTABLISHED",
        **recorded,
    }


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()


def seal_evidence_bundle(body: dict[str, Any]) -> dict[str, Any]:
    """Hash the bundle once. Later edits fail the seal."""
    material = {
        key: value
        for key, value in body.items()
        if key not in {"evidence_sha256", "immutable"}
    }
    sealed = {
        **material,
        "evidence_version": EVIDENCE_VERSION,
        "sealed_at": body.get("sealed_at") or datetime.now(UTC).isoformat(),
        "clinically_verified": False,
        "immutable": True,
    }
    digest_body = {
        key: value for key, value in sealed.items() if key not in {"evidence_sha256", "immutable"}
    }
    sealed["evidence_sha256"] = hashlib.sha256(_canonical(digest_body)).hexdigest()
    return sealed


def evidence_intact(bundle: dict[str, Any] | None) -> bool:
    if not isinstance(bundle, dict) or not bundle.get("immutable"):
        return False
    recorded = bundle.get("evidence_sha256")
    recomputed = seal_evidence_bundle(
        {key: value for key, value in bundle.items() if key != "evidence_sha256"}
    )
    return recorded == recomputed["evidence_sha256"] and recorded is not None


def refuse_evidence_mutation(existing: dict[str, Any] | None) -> None:
    if isinstance(existing, dict) and existing.get("immutable"):
        raise EvidenceImmutableError("A completed evidence bundle is immutable.")


def build_evidence_bundle(
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
    preprocessing_executed: bool,
    inference_duration_ms: float | None,
    peak_memory_bytes: int | None,
    raw_model_output_reference: str | None,
    instance_generation: dict[str, Any] | None,
    output_statistics: dict[str, Any],
    technical_validation: dict[str, Any],
    real_inference: bool,
    blocked: bool,
    blocker: dict[str, Any] | None,
    inference_kind: str,
) -> dict[str, Any]:
    """Seal one run. Blocked runs keep inference measurements null."""
    kind = "inference_run" if real_inference and not blocked else (
        "blocked_run" if blocked else inference_kind or "not_run"
    )
    return seal_evidence_bundle(
        {
            "run_id": run_id,
            "case_id": case_id,
            "prepared_input_sha256": prepared_input_sha256,
            "input_mesh": input_mesh,
            "model_sha256": model_sha256,
            "backend": {"name": backend_name, "version": backend_version},
            "runtime_manifest": runtime_manifest,
            "execution_device": device if real_inference else None,
            "preprocessing_parameters": {
                "executed": bool(preprocessing_executed and real_inference),
                "values": None,
            },
            "inference_duration_ms": inference_duration_ms if real_inference else None,
            "peak_memory_bytes": peak_memory_bytes if real_inference else None,
            "raw_model_output_reference": raw_model_output_reference if not blocked else None,
            "instance_generation": instance_generation if not blocked else None,
            "output_statistics": output_statistics,
            "technical_validation": technical_validation,
            "quality_evaluation": quality_evaluation(ground_truth_present=False),
            "real_inference": bool(real_inference),
            "blocked": blocked,
            "blocker": blocker,
            "inference_kind": inference_kind,
            "kind": kind,
            "clinical_accuracy": "NOT_ESTABLISHED",
        }
    )


def evaluate_inference_gates(
    *,
    self_test: dict[str, Any],
    input_gate: dict[str, Any],
    model_sha256: str | None,
    input_sha256: str | None,
    expected_input_sha256: str | None,
    contract_valid: bool,
    capability_executable: bool,
) -> dict[str, Any]:
    """Stop before inference when any gate fails."""
    blockers: list[str] = []
    if self_test.get("state") != "READY_FOR_INFERENCE":
        blockers.append(str(self_test.get("state") or "ENVIRONMENT_UNAVAILABLE"))
    if not input_gate.get("accepted"):
        blockers.append("INPUT_CONTRACT_INVALID")
    if model_sha256 != PINNED_CHECKPOINT_SHA256:
        blockers.append("MODEL_UNAVAILABLE")
    if not expected_input_sha256 or input_sha256 != expected_input_sha256:
        blockers.append("INPUT_CONTRACT_INVALID")
    if not contract_valid:
        blockers.append("MODEL_CONTRACT_INVALID")
    if not capability_executable:
        if self_test.get("state") == "READY_FOR_INFERENCE":
            blockers.append("RUNTIME_INITIALIZATION_FAILED")
        elif "ENVIRONMENT_UNAVAILABLE" not in blockers:
            blockers.append(str(self_test.get("state") or "RUNTIME_INITIALIZATION_FAILED"))
    unique = list(dict.fromkeys(blockers))
    return {
        "passed": not unique,
        "blockers": unique,
        "primary_blocker": unique[0] if unique else None,
        "entered_inference": False,
        "real_inference": False,
        "clinically_verified": False,
    }


def _prepared_path(artifact: dict[str, Any]) -> str:
    session = artifact.get("preparation") if isinstance(artifact.get("preparation"), dict) else {}
    active = session.get("active") if isinstance(session.get("active"), dict) else {}
    return str(active.get("output_path") or "")


def run_backend_self_test() -> dict[str, Any]:
    """Probe the host. Does not require a patient case and does not run inference."""
    from engines.segmentation.fv03_pipeline import detect_tin_capability

    capability = detect_tin_capability(refresh=True)
    self_test = capability.get("self_test") or classify_self_test(capability)
    manifest = capability.get("runtime_manifest") or {}
    return {
        "self_test": self_test,
        "runtime_manifest": manifest,
        "capability_state": capability.get("capability_state"),
        "applicable_states": capability.get("applicable_states"),
        "availability": capability.get("availability"),
        "executable": bool(capability.get("executable")),
        "model_sha256": capability.get("model_sha256"),
        "real_inference": False,
        "entered_inference": False,
        "clinically_verified": False,
        "fixture_selected": False,
        "environment": environment_specification(),
        "manual_segmentation": manual_segmentation_contract(),
        "quality_evaluation": quality_evaluation(ground_truth_present=False),
    }


def run_real_segmentation_command(artifact: dict[str, Any], *, case_id: str) -> dict[str, Any]:
    """Single real-inference path. A failed gate does not call the network."""
    from pathlib import Path

    from engines.segmentation.fv03_pipeline import (
        ToothInstanceNetBackend,
        assess_segmentation_input,
    )

    probed = run_backend_self_test()
    gate = assess_segmentation_input(artifact)
    decision = evaluate_inference_gates(
        self_test=probed["self_test"],
        input_gate=gate,
        model_sha256=probed.get("model_sha256"),
        input_sha256=gate.get("prepared_sha256"),
        expected_input_sha256=gate.get("prepared_sha256"),
        contract_valid=bool(probed["self_test"].get("contract_metadata_valid")),
        capability_executable=bool(probed.get("executable")),
    )
    record = {
        **decision,
        "case_id": case_id,
        "self_test": probed["self_test"],
        "runtime_manifest": probed["runtime_manifest"],
        "capability_state": probed.get("capability_state"),
        "input_gate": {"accepted": gate.get("accepted"), "reasons": gate.get("reasons")},
        "quality_evaluation": quality_evaluation(ground_truth_present=False),
        "manual_segmentation": manual_segmentation_contract(),
    }
    if not decision["passed"]:
        record["blocker"] = {
            "code": decision["primary_blocker"],
            "blockers": decision["blockers"],
            "message": "Inference was not entered.",
        }
        return record
    produced = ToothInstanceNetBackend().execute(
        Path(_prepared_path(artifact)),
        prepared_sha256=str(gate.get("prepared_sha256")),
    )
    real = bool(produced.get("real_inference")) and not produced.get("blocked")
    record["entered_inference"] = True
    record["real_inference"] = real
    record["clinically_verified"] = False
    record["produced_status"] = produced.get("status")
    record["inference_kind"] = produced.get("inference_kind")
    return record


def execute_named_mock_contract(
    artifact: dict[str, Any],
    *,
    self_test_state: str,
) -> dict[str, Any]:
    """Test-only success path. The mock stays named and is not real inference."""
    from pathlib import Path

    from engines.segmentation.fv03_pipeline import (
        DeterministicMockBackend,
        assess_segmentation_input,
    )

    backend = DeterministicMockBackend()
    gate = assess_segmentation_input(artifact)
    if self_test_state != "READY_FOR_INFERENCE" or not gate.get("accepted"):
        return {
            "entered_inference": False,
            "real_inference": False,
            "clinically_verified": False,
            "backend_name": backend.name,
            "inference_kind": "mock_contract",
            "blocker": (
                self_test_state
                if self_test_state != "READY_FOR_INFERENCE"
                else "INPUT_CONTRACT_INVALID"
            ),
        }
    produced = backend.execute(
        Path(_prepared_path(artifact)),
        prepared_sha256=str(gate.get("prepared_sha256")),
    )
    return {
        "entered_inference": True,
        "real_inference": bool(produced.get("real_inference")),
        "clinically_verified": False,
        "backend_name": backend.name,
        "inference_kind": produced.get("inference_kind"),
        "instance_count": len(produced.get("groups") or []),
        "fixture": False,
    }
