#!/usr/bin/env python3
"""Prepare or execute one external ToothInstanceNet inference bundle.

Without --execute this process only prints the protocol. It does not infer.
With --execute, inference runs only when CUDA, pointops, the pinned checkpoint,
and the official TeethSegDataset pipeline are available. CPU forward is refused.
The adapter prepare_mesh approximation is not used.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.segmentation.fv03_2_external_run import (  # noqa: E402
    BUNDLE_FILES,
    external_run_status,
    run_external_inference,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="FV-03.2 external CUDA inference bundle")
    parser.add_argument("--execute", action="store_true", help="Run inference on this CUDA host")
    parser.add_argument("--prepared-mesh", type=Path, required=False)
    parser.add_argument("--case-id", default="")
    parser.add_argument("--arch", choices=["upper", "lower"], default="upper")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Explicit RNG seed for this run. The verified reproducibility seed is 123456.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "external_inference_bundle",
    )
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"protocol": external_run_status(), "bundle_files": list(BUNDLE_FILES)}, indent=2))
        print("Inference was not started. Re-run with --execute on the qualified CUDA host.")
        return 0
    if args.prepared_mesh is None or not args.case_id:
        print("`--prepared-mesh` and `--case-id` are required with --execute.", file=sys.stderr)
        return 2
    status = run_external_inference(
        prepared_mesh=args.prepared_mesh,
        case_id=args.case_id,
        arch=args.arch,
        output_dir=args.output,
        seed=args.seed,
        execute=True,
    )
    print(json.dumps({key: status[key] for key in status if key != "detail"}, indent=2, default=str))
    return 0 if status.get("GENUINE_EXTERNAL_INFERENCE_COMPLETED") else 3


if __name__ == "__main__":
    raise SystemExit(main())
