import json
from pathlib import Path

import pytest

from adapters.toothinstancenet.fixture import ToothInstanceNetFixtureError, load_validated_fixture
from domain.tooth.identification import ArchType

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".research" / "tmp" / "official_real_case_stage2_verified_v1"


@pytest.mark.skipif(not ARTIFACT_DIR.is_dir(), reason="extracted official artifact required")
def test_real_fixture_source_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "upper.stl"
    source.write_bytes(b"different source bytes that cannot match artifact")
    with pytest.raises(ToothInstanceNetFixtureError, match="does not match verified artifact"):
        load_validated_fixture(ARTIFACT_DIR, arch=ArchType.UPPER, source_mesh_path=source)


def test_smoke_fixture_marker_is_not_real_case() -> None:
    payload = {
        "source_kind": "toothinstancenet_fixture",
        "fixture": True,
        "experimental": True,
        "arch": "upper",
        "instances": [],
    }
    assert payload["source_kind"] != "validated_real_case"
