#!/usr/bin/env python3
"""FV-03.1 real segmentation command.

Runs the backend self-test and the prepared-input probe for a scan.
Inference is entered only when the runtime self-test is READY_FOR_INFERENCE.
This process does not install PyTorch or CUDA.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.segmentation.fv03_1_runtime import run_backend_self_test  # noqa: E402
from engines.segmentation.fv03_pipeline import measure_segmentation_capability  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="FV-03.1 segmentation runtime self-test")
    parser.add_argument(
        "--scan",
        type=Path,
        default=ROOT / "data/benchmark/real-case/upper.stl",
        help="Scan for the prepared-input probe. Inference waits for a ready self-test.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / ".research/tmp/fv03_1_report.json",
    )
    args = parser.parse_args()
    probed = run_backend_self_test()
    measurement = None
    if args.scan.is_file():
        measurement = measure_segmentation_capability(
            args.scan, ROOT / ".research/tmp/fv03_1_reliability"
        )
    ready = probed["self_test"]["state"] == "READY_FOR_INFERENCE"
    entered = bool(measurement and measurement.get("inference_attempted") and ready)
    real_inference = bool(measurement and measurement.get("real_inference") and entered)
    report = {
        "self_test": probed,
        "prepared_input_probe": measurement,
        "command": {
            "self_test_state": probed["self_test"]["state"],
            "entered_inference": entered,
            "real_inference": real_inference,
            "clinically_verified": False,
            "primary_blocker": None if ready else probed["self_test"]["state"],
        },
        "real_inference": real_inference,
        "clinically_verified": False,
        "clinical_accuracy": "NOT_ESTABLISHED",
        "prior_blocked_run_preserved": {
            "source": ".research/tmp/fv03_report.json",
            "prepared_mesh_load_ms": 145.5,
            "input_gate_ms": 326.3,
            "capability_detection_ms": 1511.3,
            "inference": "not run",
            "peak_rss_mb": 529.3,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        f"self_test={probed['self_test']['state']} "
        f"real_inference={real_inference} report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
