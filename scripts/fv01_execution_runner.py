#!/usr/bin/env python3
"""Print the FV-01.1 execution report and exit with its machine-readable state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.segmentation.fv01_execution import run_fv01_execution  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="FV-01.1 ToothInstanceNet execution report")
    parser.add_argument(
        "--stl",
        type=Path,
        default=None,
        help="Real STL to segment when the runtime is READY",
    )
    parser.add_argument(
        "--run-inference",
        action="store_true",
        help="Attempt production inference. Refused unless the runtime is READY.",
    )
    parser.add_argument("--no-hash", action="store_true", help="Skip the checkpoint SHA-256")
    args = parser.parse_args()
    report = run_fv01_execution(
        hash_checkpoint=not args.no_hash,
        attempt_inference=args.run_inference,
        stl_path=args.stl,
    )
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
