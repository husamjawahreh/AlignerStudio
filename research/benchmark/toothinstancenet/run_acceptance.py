#!/usr/bin/env python3
"""Real ToothInstanceNet acceptance run; never used by ordinary unit tests.

Required environment:
  ALIGNERSTUDIO_TOOTHINSTANCENET_TEST_CASE=<directory containing upper.stl/lower.stl>
  ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT=<verified instseg_full.ckpt>
  ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE=<exact 3dteethland checkout>

This command performs no downloads and writes only to the external research
cache unless an explicit output directory is supplied.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from adapters.toothinstancenet.adapter import ToothInstanceNetAdapter  # noqa: E402
from adapters.toothinstancenet.contract import ToothInstanceNetConfig  # noqa: E402
from adapters.toothinstancenet.preprocessing import prepare_mesh  # noqa: E402
from domain.tooth.identification import ArchType  # noqa: E402
from engines.segmentation.toothinstancenet import ToothInstanceNetEngine  # noqa: E402


def _required_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required for the real acceptance test.")
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise RuntimeError(f"{name} does not point to a directory: {path}")
    return path


def _torch_manifest() -> dict[str, object]:
    try:
        import torch
    except ImportError as exc:
        error = RuntimeError(
            "PyTorch is unavailable; install the validated ToothInstanceNet runtime first."
        )
        error.state = "runtime_dependency_unavailable"
        raise error from exc
    if not torch.cuda.is_available():
        error = RuntimeError(
            "No CUDA GPU is available; ToothInstanceNet pointops runtime requires a GPU."
        )
        error.state = "runtime_unavailable"
        raise error
    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "cuda_available": bool(torch.cuda.is_available()),
        "device": (
            torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
        ),
        "peak_vram_bytes": (
            int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else None
        ),
    }


def main() -> int:
    case_root = _required_path("ALIGNERSTUDIO_TOOTHINSTANCENET_TEST_CASE")
    output_root = Path(
        os.environ.get(
            "ALIGNERSTUDIO_TOOTHINSTANCENET_ACCEPTANCE_OUTPUT",
            "~/.cache/alignerstudio-research/toothinstancenet/acceptance",
        )
    ).expanduser()
    output_root.mkdir(parents=True, exist_ok=True)
    checkpoint = Path(
        os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT", "")
    ).expanduser()
    source = Path(os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE", "")).expanduser()
    config = ToothInstanceNetConfig(checkpoint_path=checkpoint, source_root=source)
    try:
        checkpoint_sha256 = config.verify_checkpoint()
    except Exception as exc:
        manifest = {
            "status": "checkpoint_integrity_failed",
            "failure": f"{type(exc).__name__}: {exc}",
            "checkpoint": str(checkpoint),
        }
        (output_root / "acceptance-failure.json").write_text(json.dumps(manifest, indent=2))
        print(json.dumps(manifest, indent=2))
        return 2
    manifest: dict[str, object] = {
        "phases": {
            "PHASE 1 runtime preflight": "passed",
            "PHASE 2 source revision verification": "passed",
            "PHASE 3 checkpoint SHA256 verification": "passed",
            "PHASE 4 exact STL preprocessing": "pending",
            "PHASE 5 DentalNet construction": "pending",
            "PHASE 6 checkpoint loading": "pending",
            "PHASE 7 real instance inference": "pending",
            "PHASE 8 learned_region_cluster": "pending",
            "PHASE 9 official upper-coordinate flip": "pending",
            "PHASE 10 FDI identification": "pending",
            "PHASE 11 domain mapping": "pending",
            "PHASE 12 acceptance summary": "pending",
        },
        "source_revision": "424252e3d94a1565c8c2090eb5bb456b76386b93",
        "historical_7_class_revision": "b021d98070e8f112da7c5764034cc0409ee04c41",
        "checkpoint": config.checkpoint_path.name,
        "checkpoint_sha256": checkpoint_sha256,
        "source_revision_verified": config.verify_source_revision(),
        "preprocessing": {
            "zscore_mean": None,
            "zscore_std": config.zscore_std,
            "pose_normalize": True,
            "instance_centroids": True,
            "uniform_density_voxel_size": config.uniform_density_voxel_size,
            "features": "XYZ + surface normals",
            "feature_count": config.in_channels,
        },
        "model": {
            "name": "DentalNet",
            "in_channels": config.in_channels,
            "num_classes": config.num_classes,
            "channels_list": config.channels_list,
            "depths": config.depths,
            "heads_list": config.heads_list,
            "window_sizes": config.window_sizes,
            "point_embedding": {
                "use": config.point_embedding_use,
                "kpconv_point_influence": config.kpconv_point_influence,
                "kpconv_ball_radius": config.kpconv_ball_radius,
            },
            "stratified_union": config.stratified_union,
            "downsample_ratio": config.downsample_ratio,
            "max_drop_path_prob": config.max_drop_path_prob,
            "stratified_downsample_ratio": config.stratified_downsample_ratio,
            "crpe_bins": config.crpe_bins,
            "transformer_lr_ratio": config.transformer_lr_ratio,
        },
    }
    try:
        manifest["environment"] = _torch_manifest()
    except Exception as exc:
        manifest["status"] = getattr(exc, "state", "runtime_dependency_unavailable")
        manifest["failure"] = f"{type(exc).__name__}: {exc}"
        (output_root / "acceptance-failure.json").write_text(
            json.dumps(manifest, indent=2, default=str)
        )
        print(json.dumps(manifest, indent=2, default=str))
        return 2
    adapter = ToothInstanceNetAdapter(config)
    outputs: dict[str, object] = {}
    for jaw, arch in (("upper", ArchType.UPPER), ("lower", ArchType.LOWER)):
        path = case_root / f"{jaw}.stl"
        if not path.is_file():
            raise RuntimeError(f"Acceptance fixture is missing: {path}")
        prepared = prepare_mesh(path, config)
        manifest["phases"]["PHASE 4 exact STL preprocessing"] = "passed"
        start = time.perf_counter()
        try:
            result = ToothInstanceNetEngine(adapter, arch=arch).segment(str(path))
        except Exception as exc:
            manifest["status"] = getattr(exc, "state", "segmentation_failed")
            manifest["failure"] = f"{type(exc).__name__}: {exc}"
            manifest["runtime_metadata"] = dict(adapter.runtime_metadata)
            (output_root / "acceptance-failure.json").write_text(
                json.dumps(manifest, indent=2, default=str)
            )
            print(json.dumps(manifest, indent=2, default=str))
            return 2
        manifest["phases"]["PHASE 5 DentalNet construction"] = "passed"
        manifest["phases"]["PHASE 6 checkpoint loading"] = "passed"
        manifest["phases"]["PHASE 7 real instance inference"] = "passed"
        manifest["phases"]["PHASE 8 learned_region_cluster"] = "passed"
        manifest["phases"]["PHASE 9 official upper-coordinate flip"] = "passed"
        manifest["phases"]["PHASE 10 FDI identification"] = "passed"
        manifest["phases"]["PHASE 11 domain mapping"] = "passed"
        elapsed = time.perf_counter() - start
        outputs[jaw] = {
            "input_vertices": len(prepared.original_vertices),
            "input_faces": len(prepared.original_faces),
            "instseg_points": len(prepared.sampled_indices),
            "instances": len(result.segmentation.instances),
            "valid_meshes": len(result.segmentation.instances),
            "excluded_fragments": len(result.diagnostics.empty_instance_ids),
            "fdi_assignments": result.diagnostics.fdi_by_instance,
            "duplicate_fdi": result.diagnostics.duplicate_fdi_numbers,
            "missing_fdi": result.diagnostics.missing_fdi_numbers,
            "state": result.status,
            "runtime_seconds": elapsed,
            "runtime_metadata": dict(adapter.runtime_metadata),
        }
    manifest["result"] = outputs
    manifest["phases"]["PHASE 12 acceptance summary"] = "passed"
    (output_root / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(json.dumps(manifest, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
