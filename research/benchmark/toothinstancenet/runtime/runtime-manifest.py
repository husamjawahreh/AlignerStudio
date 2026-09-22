#!/usr/bin/env python3
"""Print the reproducible ToothInstanceNet runtime manifest."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

EXPECTED_SOURCE = "424252e3d94a1565c8c2090eb5bb456b76386b93"
EXPECTED_CHECKPOINT = "100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803"
POINTOPS_SYMBOLS = (
    "farthestPointSampling",
    "ballQuery",
    "kNNQuery",
    "stratifiedQueryKeyPairs",
    "aggregateValuesCRPE_forward",
    "aggregateValuesCRPE_backward",
    "attentionLogitsCRPE_forward",
    "attentionLogitsCRPE_backward",
)


def version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> None:
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        raise SystemExit("runtime_unavailable: nvidia-smi is not available in the container")
    try:
        nvidia_output = subprocess.check_output(
            [nvidia_smi, "--query-gpu=name,driver_version", "--format=csv,noheader"],
            text=True,
        ).strip()
    except Exception as exc:  # noqa: BLE001 - preflight boundary
        raise SystemExit(f"runtime_unavailable: nvidia-smi failed: {exc}") from exc
    source = Path(os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE", "/opt/3dteethland"))
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != EXPECTED_SOURCE:
        raise SystemExit(f"source_revision_mismatch: {revision} != {EXPECTED_SOURCE}")
    checkpoint = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT")
    if not checkpoint:
        raise SystemExit("checkpoint_integrity_failed: checkpoint environment variable is missing")
    checkpoint_path = Path(checkpoint)
    if not checkpoint_path.is_file():
        raise SystemExit(f"checkpoint_integrity_failed: missing checkpoint {checkpoint_path}")
    import hashlib

    checkpoint_sha256 = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    if checkpoint_sha256 != EXPECTED_CHECKPOINT:
        raise SystemExit(
            f"checkpoint_integrity_failed: {checkpoint_sha256} != {EXPECTED_CHECKPOINT}"
        )
    try:
        import pointops
        import torch
    except ImportError as exc:
        raise SystemExit(f"runtime_dependency_unavailable: {exc}") from exc
    if not torch.cuda.is_available():
        raise SystemExit("runtime_unavailable: torch.cuda.is_available() is false")
    missing_symbols = [name for name in POINTOPS_SYMBOLS if not hasattr(pointops, name)]
    if missing_symbols:
        raise SystemExit(f"runtime_dependency_unavailable: pointops missing {missing_symbols}")
    manifest = {
        "python": platform.python_version(),
        "pytorch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu_available": bool(torch.cuda.is_available()),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "nvidia_smi": nvidia_output,
        "torch_scatter": version("torch-scatter"),
        "pointops": "0.0.0 from 3dteethland pointops CUDAExtension",
        "open3d": version("open3d"),
        "pymeshlab": version("pymeshlab"),
        "gco_wrapper": version("gco-wrapper"),
        "toothinstancenet_source_revision": revision,
        "checkpoint_path": os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT"),
        "checkpoint_sha256": checkpoint_sha256,
        "pointops_symbols": list(POINTOPS_SYMBOLS),
    }
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
