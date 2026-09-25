"""Deterministic ToothInstanceNet runtime readiness. Does not install or switch backends."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from adapters.toothinstancenet.contract import ToothInstanceNetConfig

CHECKPOINT_SHA256 = ToothInstanceNetConfig.checkpoint_sha256
SOURCE_REVISION = ToothInstanceNetConfig.source_revision
VALIDATED_PYTHON = "3.12"
VALIDATED_TORCH = "2.10.0+cu128"
VALIDATED_CUDA_IMAGE = "12.8.1"
UPSTREAM_TORCH = "2.3.0"
UPSTREAM_CUDA = "12.1"


class ReadinessState(StrEnum):
    READY = "ready"
    BLOCKED_BY_ENVIRONMENT = "blocked_by_environment"
    MISCONFIGURED = "misconfigured"
    MODEL_MISSING = "model_missing"
    DEPENDENCY_MISSING = "dependency_missing"


@dataclass(frozen=True)
class ReadinessFinding:
    code: str
    state: ReadinessState
    detail: str
    blocking: bool = True


@dataclass(frozen=True)
class ToothInstanceNetReadiness:
    state: ReadinessState
    configured_backend: str
    backend_changed: bool
    python_version: str
    checkpoint_sha256_expected: str
    source_revision_expected: str
    gpu_memory_mib: int | None
    findings: tuple[ReadinessFinding, ...]
    requirements: tuple[str, ...]

    def payload(self) -> dict:
        body = asdict(self)
        body["state"] = self.state.value
        body["findings"] = [
            {"code": item.code, "state": item.state.value, "detail": item.detail}
            for item in self.findings
        ]
        return body


def _module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


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


def _nvidia_driver_visible() -> bool:
    completed = _run(["nvidia-smi", "-L"])
    return completed is not None and completed.returncode == 0 and bool(completed.stdout.strip())


def _nvcc_present() -> bool:
    completed = _run(["nvcc", "--version"])
    return completed is not None and completed.returncode == 0


def _gpu_memory_mib() -> int | None:
    completed = _run(
        ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]
    )
    if completed is None or completed.returncode != 0:
        return None
    line = completed.stdout.strip().splitlines()
    if not line:
        return None
    try:
        return int(line[0].strip())
    except ValueError:
        return None


def _git_head(source: Path) -> str | None:
    completed = _run(["git", "-C", str(source), "rev-parse", "HEAD"])
    if completed is None or completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _primary_state(findings: tuple[ReadinessFinding, ...]) -> ReadinessState:
    states = {item.state for item in findings if item.blocking}
    if ReadinessState.BLOCKED_BY_ENVIRONMENT in states:
        return ReadinessState.BLOCKED_BY_ENVIRONMENT
    if ReadinessState.DEPENDENCY_MISSING in states:
        return ReadinessState.DEPENDENCY_MISSING
    if ReadinessState.MODEL_MISSING in states:
        return ReadinessState.MODEL_MISSING
    if ReadinessState.MISCONFIGURED in states:
        return ReadinessState.MISCONFIGURED
    return ReadinessState.READY


def diagnose_toothinstancenet_readiness() -> ToothInstanceNetReadiness:
    """Inspect the host. Never sets ALIGNERSTUDIO_SEGMENTATION_BACKEND."""
    before = os.environ.get("ALIGNERSTUDIO_SEGMENTATION_BACKEND")
    findings: list[ReadinessFinding] = []
    checkpoint = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT", "").strip()
    source = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE", "").strip()
    checkpoint_path = Path(checkpoint) if checkpoint else None
    source_path = Path(source) if source else None

    if not _nvidia_driver_visible():
        findings.append(
            ReadinessFinding(
                "nvidia_driver",
                ReadinessState.BLOCKED_BY_ENVIRONMENT,
                "nvidia-smi cannot communicate with an NVIDIA driver.",
            )
        )
    if _gpu_memory_mib() is None:
        findings.append(
            ReadinessFinding(
                "gpu_memory",
                ReadinessState.BLOCKED_BY_ENVIRONMENT,
                "GPU memory is not visible. CUDA inference cannot be measured.",
            )
        )
    if not _nvcc_present():
        findings.append(
            ReadinessFinding(
                "nvcc",
                ReadinessState.BLOCKED_BY_ENVIRONMENT,
                "nvcc is not on PATH. It is required to compile pointops, not to "
                "run an already-built extension.",
                blocking=False,
            )
        )
    if not _module_present("torch"):
        findings.append(
            ReadinessFinding(
                "torch",
                ReadinessState.DEPENDENCY_MISSING,
                f"PyTorch is not installed. Validated image uses {VALIDATED_TORCH}. "
                f"Upstream 3dteethland docs also cite {UPSTREAM_TORCH}.",
            )
        )
    if not _module_present("pointops"):
        findings.append(
            ReadinessFinding(
                "pointops",
                ReadinessState.DEPENDENCY_MISSING,
                "pointops is not installed. It is a CUDA extension. CPU inference "
                "is not supported.",
            )
        )
    if checkpoint_path is None or not checkpoint_path.is_file():
        findings.append(
            ReadinessFinding(
                "checkpoint",
                ReadinessState.MODEL_MISSING,
                "ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT is unset or is not a file. "
                f"Expected SHA-256 {CHECKPOINT_SHA256}.",
            )
        )
    if source_path is None or not source_path.is_dir():
        findings.append(
            ReadinessFinding(
                "source",
                ReadinessState.MODEL_MISSING,
                "ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE is unset or is not a directory. "
                f"Expected revision {SOURCE_REVISION}.",
            )
        )
    else:
        head = _git_head(source_path)
        if head not in {None, SOURCE_REVISION}:
            findings.append(
                ReadinessFinding(
                    "source_revision",
                    ReadinessState.MISCONFIGURED,
                    f"Source HEAD {head} does not match {SOURCE_REVISION}.",
                )
            )
    python_ok = sys.version_info[:2] == tuple(int(part) for part in VALIDATED_PYTHON.split("."))
    if not python_ok:
        findings.append(
            ReadinessFinding(
                "python",
                ReadinessState.MISCONFIGURED,
                f"Python {sys.version.split()[0]} is not the validated {VALIDATED_PYTHON}.",
            )
        )

    after = os.environ.get("ALIGNERSTUDIO_SEGMENTATION_BACKEND")
    requirements = (
        f"Python {VALIDATED_PYTHON}",
        f"PyTorch {VALIDATED_TORCH} (validated) or {UPSTREAM_TORCH} (upstream docs)",
        f"CUDA {VALIDATED_CUDA_IMAGE} image, or {UPSTREAM_CUDA} cited upstream",
        "NVIDIA driver visible to nvidia-smi",
        "pointops CUDA extension",
        f"checkpoint SHA-256 {CHECKPOINT_SHA256}",
        f"source revision {SOURCE_REVISION}",
        "ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet to select it; "
        "this diagnostic does not set that variable",
    )
    return ToothInstanceNetReadiness(
        state=_primary_state(tuple(findings)),
        configured_backend=(before or "onnx").strip().lower(),
        backend_changed=before != after,
        python_version=sys.version.split()[0],
        checkpoint_sha256_expected=CHECKPOINT_SHA256,
        source_revision_expected=SOURCE_REVISION,
        gpu_memory_mib=_gpu_memory_mib(),
        findings=tuple(findings),
        requirements=requirements,
    )
