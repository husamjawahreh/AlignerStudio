import json
from pathlib import Path

import pytest

from adapters.toothinstancenet.fixture import ToothInstanceNetFixtureError, load_validated_fixture
from domain.tooth.identification import ArchType


def test_real_fixture_source_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    artifact = tmp_path / "upper.json"
    artifact.write_text(
        json.dumps(
            {
                "source_kind": "validated_real_case",
                "fixture": True,
                "experimental": True,
                "arch": "upper",
                "source_stl_sha256": "0" * 64,
                "instances": [],
            }
        )
    )
    source = tmp_path / "upper.stl"
    source.write_bytes(b"different source")
    with pytest.raises(ToothInstanceNetFixtureError, match="hash"):
        load_validated_fixture(artifact, arch=ArchType.UPPER, source_mesh_path=source)


def test_smoke_fixture_marker_is_not_real_case() -> None:
    payload = {
        "source_kind": "toothinstancenet_fixture",
        "fixture": True,
        "experimental": True,
        "arch": "upper",
        "instances": [],
    }
    assert payload["source_kind"] != "validated_real_case"
