#!/usr/bin/env python3
"""Independent audit for a generated ToothInstanceNet real-case package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

EXPECTED = {
    "upper": "60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48",
    "lower": "dc4f8b0d4e8d1c21ab45ee0e69457eb575b869bcd895fbda36de9fcb4387037b",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    args = parser.parse_args()
    root = args.artifact_dir
    manifest = json.loads((root / "artifact-manifest.json").read_text())
    assert manifest["source_kind"] == "validated_real_case"
    assert manifest["fixture"] is True and manifest["experimental"] is True
    assert manifest["checkpoint_sha256"] == args.checkpoint_sha256
    assert (root / "selected_to_original_vertex_mapping.npz").is_file()
    assert (root / "exact_instseg_coordinates.npz").is_file()
    np.load(root / "selected_to_original_vertex_mapping.npz", allow_pickle=False)
    np.load(root / "exact_instseg_coordinates.npz", allow_pickle=False)
    for jaw in ("upper", "lower"):
        assert sha256(args.input_dir / f"{jaw}.stl") == EXPECTED[jaw]
        payload = json.loads((root / jaw / f"CASE_{jaw}.json").read_text())
        assert payload["source_kind"] == "validated_real_case"
        assert payload["fixture"] is True and payload["experimental"] is True
        assert payload["source_stl_sha256"] == EXPECTED[jaw]
        for item in payload["instances"]:
            assert item["faces"] and item["vertices"]
            assert item["provenance"] == "experimental"
            assert item["fixture"] is True and item["experimental"] is True
    print(
        json.dumps(
            {"status": "PASS", "artifact": str(root), "source_kind": manifest["source_kind"]},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
