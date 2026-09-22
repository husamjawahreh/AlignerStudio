import json
from pathlib import Path

import pytest

from adapters.toothinstancenet.fixture import (
    ToothInstanceNetFixtureError,
    load_validated_fixture,
)
from domain.tooth.identification import ArchType


def artifact_payload(*, count: int = 28, fdis: list[int] | None = None) -> dict:
    fdis = fdis or [11 + (index % 8) for index in range(count)]
    instances = []
    for index in range(count):
        offset = float(index * 2)
        instances.append(
            {
                "instance_id": index,
                "fdi_number": fdis[index],
                "vertices": [[offset, 0.0, 0.0], [offset + 1.0, 0.0, 0.0], [offset, 1.0, 0.0]],
                "faces": [[0, 1, 2]],
                "triangle_indices": [index],
                "vertex_indices": [index * 3, index * 3 + 1, index * 3 + 2],
                "centroid": [offset + 0.333, 0.333, 0.0],
                "confidence": 0.8,
            }
        )
    return {
        "source_kind": "validated_real_case",
        "fixture": True,
        "experimental": True,
        "arch": "upper",
        "model_version": "validated-artifact-test",
        "input_faces": count,
        "empty_instance_ids": [count],
        "instances": instances,
    }


def write_artifact(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "validated-real-case.json"
    path.write_text(json.dumps(payload))
    return path


def test_validated_toothinstancenet_fixture_preserves_28_records_and_fdi(tmp_path: Path) -> None:
    result = load_validated_fixture(
        write_artifact(tmp_path, artifact_payload()), arch=ArchType.UPPER
    )
    assert len(result.segmentation.instances) == 28
    assert len(result.identification.teeth) == 28
    assert [tooth.identity.number for tooth in result.identification.teeth[:2]] == [11, 12]
    assert result.segmentation.metadata.fixture is True
    assert result.segmentation.metadata.provenance.value == "experimental"
    assert result.diagnostics.empty_instance_ids == (28,)
    assert result.diagnostics.duplicate_fdi_numbers


def test_fixture_preserves_lower_arch_and_mesh_geometry(tmp_path: Path) -> None:
    payload = artifact_payload(count=2, fdis=[31, 32])
    payload["arch"] = "lower"
    result = load_validated_fixture(write_artifact(tmp_path, payload), arch=ArchType.LOWER)
    assert result.identification.arch is ArchType.LOWER
    assert result.identification.teeth[0].identity.number == 31
    assert result.segmentation.instances[0].mesh_faces == ((0, 1, 2),)
    assert result.segmentation.instances[0].mesh_vertices[1] == (1.0, 0.0, 0.0)


def test_duplicate_and_missing_fdi_remain_diagnostic(tmp_path: Path) -> None:
    payload = artifact_payload(count=2, fdis=[11, 11])
    result = load_validated_fixture(write_artifact(tmp_path, payload), arch=ArchType.UPPER)
    assert result.diagnostics.duplicate_fdi_numbers == (11,)
    assert 12 in result.diagnostics.missing_fdi_numbers
    assert result.status == "identification_incomplete"


@pytest.mark.parametrize(
    "mutator, message",
    [
        (lambda payload: payload.pop("source_kind"), "source_kind"),
        (lambda payload: payload.update(fixture=False), "fixture"),
    ],
)
def test_fixture_requires_explicit_validated_markers(tmp_path: Path, mutator, message: str) -> None:
    payload = artifact_payload()
    mutator(payload)
    with pytest.raises(ToothInstanceNetFixtureError, match=message):
        load_validated_fixture(write_artifact(tmp_path, payload), arch=ArchType.UPPER)
