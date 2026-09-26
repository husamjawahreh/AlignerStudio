"""Print the FV-01 ToothInstanceNet probe as JSON. Does not run inference."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.segmentation.fv01_probe import run_fv01_probe  # noqa: E402


def main() -> None:
    json.dump(run_fv01_probe(), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
