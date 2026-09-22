#!/usr/bin/env python3
"""One-command Kaggle real-case ToothInstanceNet artifact workflow.

This script only succeeds from actual upstream inference outputs. It never
creates predictions, fallback geometry, or smoke-fixture data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

EXPECTED_COUNTS = {"upper": 21219, "lower": 20040}
CHECKPOINT_SHA256 = "100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803"
SOURCE_REVISION = "424252e3d94a1565c8c2090eb5bb456b76386b93"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("/kaggle/input/datasets/husamjawahreh/alignerstudio-real-case"),
    )
    parser.add_argument(
        "--checkpoints",
        type=Path,
        default=Path("/kaggle/input/datasets/husamjawahreh/toothinstancenet-checkpoints"),
    )
    parser.add_argument("--source", type=Path, default=Path("/kaggle/working/3dteethland"))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--work-dir", type=Path, default=Path("/kaggle/working/toothinstancenet-real-case-work")
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("/kaggle/working/toothinstancenet-real-case-artifact"),
    )
    parser.add_argument("--allow-count-difference", action="store_true")
    args = parser.parse_args()

    if sha256(args.checkpoints / "instseg_full.ckpt") != CHECKPOINT_SHA256:
        raise SystemExit("checkpoint_integrity_failed")
    revision = subprocess.check_output(
        ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != SOURCE_REVISION:
        raise SystemExit(f"source_revision_mismatch: {revision}")

    sys.path.insert(0, str(args.project_root.resolve()))
    from adapters.toothinstancenet.contract import ToothInstanceNetConfig
    from adapters.toothinstancenet.preprocessing import prepare_mesh

    config = ToothInstanceNetConfig(
        checkpoint_path=args.checkpoints / "instseg_full.ckpt",
        source_root=args.source,
    )
    config.verify_checkpoint()
    preprocessing_arrays = {}
    for jaw, expected in EXPECTED_COUNTS.items():
        prepared = prepare_mesh(args.input_dir / f"{jaw}.stl", config)
        actual = len(prepared.sampled_indices)
        print(json.dumps({"phase": "preprocessing", "jaw": jaw, "instseg_points": actual}))
        if actual != expected and not args.allow_count_difference:
            raise SystemExit(f"preprocessing_count_mismatch:{jaw}:{actual}!={expected}")
        args.work_dir.mkdir(parents=True, exist_ok=True)
        preprocessing_arrays[jaw] = {
            "selected_indices": prepared.sampled_indices,
            "transformed_points": prepared.transformed_points[prepared.sampled_indices],
            "transformed_normals": prepared.transformed_normals[prepared.sampled_indices],
            "original_vertices": prepared.original_vertices,
        }
    mapping = args.work_dir / "selected_to_original_vertex_mapping.npz"
    coordinates = args.work_dir / "exact_instseg_coordinates.npz"
    np.savez_compressed(
        mapping,
        **{
            f"{jaw}_{key}": value
            for jaw, arrays in preprocessing_arrays.items()
            for key, value in arrays.items()
            if key == "selected_indices"
        },
    )
    np.savez_compressed(
        coordinates,
        **{
            f"{jaw}_{key}": value
            for jaw, arrays in preprocessing_arrays.items()
            for key, value in arrays.items()
            if key != "selected_indices"
        },
    )

    runner = args.project_root / "research/benchmark/toothinstancenet/kaggle/run_benchmark.py"
    command = [
        sys.executable,
        str(runner),
        "--repo",
        str(args.source),
        "--input-dir",
        str(args.input_dir),
        "--checkpoints",
        str(args.checkpoints),
        "--work-dir",
        str(args.work_dir),
    ]
    subprocess.run(command, check=True)
    generator = (
        args.project_root
        / "research/benchmark/toothinstancenet/kaggle/generate_real_case_artifact.py"
    )
    subprocess.run(
        [
            sys.executable,
            str(generator),
            "--input-dir",
            str(args.input_dir),
            "--prediction-dir",
            str(args.work_dir),
            "--output-dir",
            str(args.artifact_dir),
            "--checkpoint",
            str(args.checkpoints / "instseg_full.ckpt"),
            "--source",
            str(args.source),
            "--selected-mapping",
            str(mapping),
            "--instseg-coordinates",
            str(coordinates),
        ],
        check=True,
    )
    audit = (
        args.project_root / "research/benchmark/toothinstancenet/kaggle/audit_real_case_artifact.py"
    )
    subprocess.run(
        [
            sys.executable,
            str(audit),
            "--artifact-dir",
            str(args.artifact_dir),
            "--input-dir",
            str(args.input_dir),
            "--checkpoint-sha256",
            CHECKPOINT_SHA256,
        ],
        check=True,
    )
    package_script = (
        args.project_root
        / "research/benchmark/toothinstancenet/kaggle/package_real_case_artifact.sh"
    )
    subprocess.run(
        ["bash", str(package_script), str(args.artifact_dir), str(args.artifact_dir) + ".zip"],
        check=True,
    )
    print(
        json.dumps(
            {"status": "REAL_CASE_ARTIFACT_READY", "artifact_zip": str(args.artifact_dir) + ".zip"},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
