#!/usr/bin/env python3
"""Research-only Kaggle harness for ToothInstanceNet.

This script never edits production files or canonical inputs. It copies inputs
into a working directory, patches a temporary upstream config, runs the
upstream inference entry point, and writes an auditable JSON report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

EXPECTED_INPUTS = {
    "upper": "60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48",
    "lower": "dc4f8b0d4e8d1c21ab45ee0e69457eb575b869bcd895fbda36de9fcb4387037b",
}
CHECKPOINT_NAMES = ("align.ckpt", "instseg_full.ckpt", "landmarks_full.ckpt")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def gpu_snapshot() -> dict[str, Any]:
    try:
        import torch

        device = torch.device("cuda:0")
        return {
            "available": bool(torch.cuda.is_available()),
            "name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "cuda_version": torch.version.cuda,
            "pytorch_version": torch.__version__,
            "total_vram_bytes": (
                int(torch.cuda.get_device_properties(0).total_memory)
                if torch.cuda.is_available()
                else None
            ),
            "allocated_peak_bytes": (
                int(torch.cuda.max_memory_allocated(device))
                if torch.cuda.is_available()
                else None
            ),
            "reserved_peak_bytes": (
                int(torch.cuda.max_memory_reserved(device))
                if torch.cuda.is_available()
                else None
            ),
        }
    except Exception as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def mesh_stats(path: Path) -> dict[str, Any]:
    import trimesh

    mesh = trimesh.load(path, process=False)
    vertices = getattr(mesh, "vertices", [])
    faces = getattr(mesh, "faces", [])
    return {
        "path": str(path),
        "vertices": int(len(vertices)),
        "faces": int(len(faces)),
        "vertex_sha256": hashlib.sha256(vertices.tobytes()).hexdigest(),
        "face_sha256": hashlib.sha256(faces.tobytes()).hexdigest(),
    }


def patch_config(source: Path, target: Path, work_root: Path, checkpoint_dir: Path) -> None:
    import yaml

    config = yaml.safe_load(source.read_text())
    config["work_dir"] = str(work_root / "logs")
    config["out_dir"] = str(work_root / "upstream-output")
    config["datamodule"]["root"] = str(work_root / "model_inputs")
    config["datamodule"]["landmarks_root"] = str(work_root / "model_inputs")
    config["datamodule"]["num_workers"] = 0
    config["datamodule"]["persistent_workers"] = False
    config["model"]["align"]["checkpoint_path"] = str(checkpoint_dir / "align.ckpt")
    config["model"]["instseg"]["checkpoint_path"] = str(checkpoint_dir / "instseg_full.ckpt")
    config["model"]["landmarks"]["checkpoint_path"] = str(checkpoint_dir / "landmarks_full.ckpt")
    target.write_text(yaml.safe_dump(config, sort_keys=False))


def copy_inputs(input_dir: Path, work_root: Path) -> dict[str, Path]:
    destination = work_root / "inputs" / "CASE"
    model_destination = work_root / "model_inputs" / "CASE"
    destination.mkdir(parents=True, exist_ok=True)
    model_destination.mkdir(parents=True, exist_ok=True)
    result = {}
    for jaw in ("upper", "lower"):
        source = input_dir / f"{jaw}.stl"
        if not source.exists():
            raise FileNotFoundError(f"Missing Kaggle input: {source}")
        actual = sha256(source)
        if actual != EXPECTED_INPUTS[jaw]:
            raise ValueError(f"{source} hash {actual} does not match canonical {EXPECTED_INPUTS[jaw]}")
        target = destination / f"CASE_{jaw}.stl"
        shutil.copy2(source, target)
        # Keep CASE working copies and separate STEM aliases for the upstream
        # filename-based jaw/FDI convention.
        shutil.copy2(target, model_destination / f"STEM_{jaw}.stl")
        result[jaw] = target
    return result


def find_json_outputs(root: Path) -> list[Path]:
    return sorted(root.rglob("CASE_*.json"))


def normalize_output_names(root: Path) -> None:
    for source in root.rglob("STEM_*.json"):
        target = source.with_name(source.name.replace("STEM_", "CASE_", 1))
        shutil.copy2(source, target)


def recursive_values(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from recursive_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from recursive_values(item)


def inspect_prediction(path: Path, original: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(path.read_text())
    labels: list[Any] = []
    fdi_values: list[int] = []
    instances = data.get("instances", []) if isinstance(data, dict) else []
    instance_sizes = []
    empty_instances = []
    if isinstance(instances, list):
        for index, instance in enumerate(instances):
            if not isinstance(instance, dict):
                continue
            points = instance.get("points", instance.get("vertices", instance.get("indices", [])))
            size = len(points) if isinstance(points, list) else None
            instance_sizes.append(size)
            if size == 0:
                empty_instances.append(index)
    for key, value in recursive_values(data):
        lower = key.lower()
        if lower in {"labels", "label", "instance_labels", "instances"} and isinstance(value, list):
            if value and all(isinstance(item, (int, float)) for item in value):
                labels = value
        if lower in {"fdi", "fdi_label", "tooth_number"} and isinstance(value, int):
            fdi_values.append(value)
    label_count = len(labels)
    correspondence = "UNKNOWN"
    if label_count == original["vertices"]:
        correspondence = "LIKELY_ORIGINAL_VERTICES_LENGTH_MATCH"
    elif label_count:
        correspondence = "SAMPLED_OR_NON_VERTEX_OUTPUT_LENGTH"
    return {
        "path": str(path),
        "json_keys": sorted(data) if isinstance(data, dict) else [],
        "label_count": label_count,
        "predicted_instances": len(instances) if isinstance(instances, list) else None,
        "instance_sizes": instance_sizes,
        "empty_instances": empty_instances,
        "fdi_labels": sorted(set(fdi_values)),
        "duplicate_fdi_labels": sorted({label for label in fdi_values if fdi_values.count(label) > 1}),
        "original_vertex_count": original["vertices"],
        "correspondence": correspondence,
        "raw_schema": data,
    }


def run(args: argparse.Namespace) -> int:
    work_root = Path(args.work_dir).resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    repo = Path(args.repo).resolve()
    checkpoint_dir = Path(args.checkpoints).resolve()
    input_paths = copy_inputs(Path(args.input_dir).resolve(), work_root)
    original_stats = {jaw: mesh_stats(path) for jaw, path in input_paths.items()}
    missing = [name for name in CHECKPOINT_NAMES if not (checkpoint_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing checkpoints: {', '.join(missing)}")

    config_path = work_root / "config.kaggle.yaml"
    patch_config(repo / "teethland/config/config.yaml", config_path, work_root, checkpoint_dir)
    command = [sys.executable, "infer.py", "landmarks", "--devices", "1", "--config", str(config_path)]
    gpu_before = gpu_snapshot()
    start = time.perf_counter()
    failure = None
    completed = None
    try:
        completed = subprocess.run(command, cwd=repo, text=True, capture_output=True, check=True)
    except subprocess.CalledProcessError as exc:
        failure = {"type": "inference_failed", "returncode": exc.returncode, "stdout": exc.stdout[-12000:], "stderr": exc.stderr[-12000:]}
    runtime = time.perf_counter() - start
    gpu_after = gpu_snapshot()
    normalize_output_names(work_root)
    outputs = []
    for path in find_json_outputs(work_root):
        jaw = "upper" if "upper" in path.name else "lower" if "lower" in path.name else None
        if jaw:
            outputs.append(inspect_prediction(path, original_stats[jaw]))
    missing_teeth = {}
    for item in outputs:
        fdi = set(item["fdi_labels"])
        if fdi:
            jaw = "upper" if "upper" in item["path"] else "lower"
            expected = (set(range(11, 19)) | set(range(21, 29))) if jaw == "upper" else (set(range(31, 39)) | set(range(41, 49)))
            missing_teeth[item["path"]] = sorted(expected - fdi)
        else:
            missing_teeth[item["path"]] = None
    report = {
        "MODEL": "ToothInstanceNet / 3dteethland",
        "CHECKPOINTS": {name: {"path": str(checkpoint_dir / name), "sha256": sha256(checkpoint_dir / name), "size_bytes": (checkpoint_dir / name).stat().st_size} for name in CHECKPOINT_NAMES},
        "GPU": gpu_after,
        "CUDA": gpu_after.get("cuda_version"),
        "INPUT_VERTICES": {jaw: stats["vertices"] for jaw, stats in original_stats.items()},
        "INPUT_FACES": {jaw: stats["faces"] for jaw, stats in original_stats.items()},
        "PREDICTED_INSTANCES": {item["path"]: item["predicted_instances"] for item in outputs},
        "FDI_LABELS": {item["path"]: item["fdi_labels"] for item in outputs},
        "MISSING_TEETH": missing_teeth,
        "DUPLICATE_TEETH": {item["path"]: item["duplicate_fdi_labels"] for item in outputs},
        "LANDMARKS": sorted(str(path) for path in work_root.rglob("*kpt.json")),
        "ORIGINAL_MESH_MAPPING": {item["path"]: item["correspondence"] for item in outputs},
        "RUNTIME_SECONDS": runtime,
        "PEAK_VRAM": gpu_after.get("allocated_peak_bytes"),
        "FAILURES": [failure] if failure else [],
        "QUALITY_ASSESSMENT": "Not a clinical or accuracy assessment; inspect raw JSON and mesh correspondence before interpretation.",
        "PRODUCTION_READY": False,
        "COMMAND": command,
        "CANONICAL_INPUTS": {jaw: {"path": str(path), "sha256": sha256(path)} for jaw, path in input_paths.items()},
        "OUTPUTS": outputs,
        "GPU_BEFORE": gpu_before,
        "COMPLETED_STDOUT": completed.stdout[-12000:] if completed else None,
    }
    (work_root / "benchmark-report.json").write_text(json.dumps(report, indent=2, default=str))
    (work_root / "benchmark-summary.md").write_text("# ToothInstanceNet Kaggle Benchmark\n\nSee `benchmark-report.json` for the machine-readable result.\n\nProduction-ready: **NO**. This is research-only and does not establish clinical validity.\n")
    return 0 if failure is None else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--input-dir", required=True, help="Directory containing upper.stl and lower.stl")
    parser.add_argument("--checkpoints", required=True)
    parser.add_argument("--work-dir", required=True)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
