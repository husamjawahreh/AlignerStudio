import hashlib
import json
import struct
from pathlib import Path

import pytest

from adapters.toothinstancenet.fixture import (
    ARTIFACT_ZIP_SHA256,
    ToothInstanceNetFixtureError,
    load_validated_fixture,
)
from domain.tooth.identification import ArchType

CONFIGURATION = {
    "m3_as_m2": True,
    "distinguish_left_right": False,
    "distinguish_upper_lower": False,
    "norm": True,
    "clean": True,
    "uniform_density_voxel_size": [0.025, 0.01],
    "stage2_iters": 0,
    "post_process_labels": False,
    "do_align": True,
}


def _stl_bytes(triangle_count: int) -> bytes:
    output = bytearray(b"AlignerStudio verified artifact".ljust(80, b" "))
    output.extend(struct.pack("<I", triangle_count))
    for index in range(triangle_count):
        x = float(index * 3)
        output.extend(struct.pack("<3f", 0.0, 0.0, 1.0))
        output.extend(struct.pack("<3f", x, 0.0, 0.0))
        output.extend(struct.pack("<3f", x + 1.0, 0.0, 0.0))
        output.extend(struct.pack("<3f", x, 1.0, 0.0))
        output.extend(struct.pack("<H", 0))
    return bytes(output)


def _labels(arch: ArchType) -> list[int]:
    start = 31 if arch is ArchType.LOWER else 11
    return [label for index in range(14) for label in (start + index // 2,) * 3] + [0] * 3


def _write_artifact(root: Path) -> Path:
    root.mkdir()
    audits = []
    for arch in (ArchType.LOWER, ArchType.UPPER):
        (root / f"{arch.value}.stl").write_bytes(_stl_bytes(15))
        instance_values = [value for value in range(14) for _ in range(3)] + [-1] * 3
        label_values = _labels(arch)
        (root / f"{arch.value}.json").write_text(
            json.dumps({"instances": instance_values, "labels": label_values})
        )
        audits.append(
            {
                "arch": arch.value,
                "instances_length": len(instance_values),
                "labels_length": len(label_values),
                "unique_instances": [-1, *range(14)],
                "unique_labels": sorted(set(label_values)),
                "instance_to_label": {str(index): label_values[index * 3] for index in range(14)},
                "expected_labels": sorted(set(label_values) - {0}),
                "semantic_pass": True,
            }
        )
    (root / "manifest.json").write_text(
        json.dumps({"stage": "instances", "configuration": CONFIGURATION, "semantic_audit": audits})
    )
    (root / "README.md").write_text("fixture")
    lines = []
    for name in (
        "README.md",
        "lower.json",
        "lower.stl",
        "manifest.json",
        "upper.json",
        "upper.stl",
    ):
        lines.append(f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}")
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
    return root


def _rewrite_checksums(root: Path, changed: str) -> None:
    lines = []
    for line in (root / "SHA256SUMS.txt").read_text().splitlines():
        digest, _, name = line.partition("  ")
        if name == changed:
            digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")


def _rewrite_json(root: Path, name: str, mutate) -> None:
    path = root / name
    payload = json.loads(path.read_text())
    mutate(payload)
    path.write_text(json.dumps(payload))
    _rewrite_checksums(root, name)


def _rewrite_manifest(root: Path, mutate) -> None:
    path = root / "manifest.json"
    payload = json.loads(path.read_text())
    mutate(payload)
    path.write_text(json.dumps(payload))
    _rewrite_checksums(root, "manifest.json")


def test_valid_verified_per_vertex_artifact_reconstructs_meshes(tmp_path: Path) -> None:
    result = load_validated_fixture(_write_artifact(tmp_path / "artifact"), arch=ArchType.UPPER)
    assert len(result.segmentation.instances) == 14
    assert result.segmentation.instances[0].mesh_faces == ((0, 1, 2),)
    assert result.segmentation.instances[0].mesh_vertices[1] == (1.0, 0.0, 0.0)
    assert result.identification.teeth[0].identity is None
    assert "semantic_label=11" in result.identification.teeth[0].notes
    assert "correspondence_verified=true" in result.segmentation.metadata.notes


def test_verified_zip_extracts_and_loads() -> None:
    archive = Path("official_real_case_stage2_verified_v1.zip")
    if not archive.is_file():
        pytest.skip("verified artifact ZIP is not present")
    result = load_validated_fixture(archive, arch=ArchType.UPPER)
    assert len(result.segmentation.instances) == 14
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARTIFACT_ZIP_SHA256


def test_bad_checksum_fails(tmp_path: Path) -> None:
    root = _write_artifact(tmp_path / "artifact")
    (root / "upper.json").write_text((root / "upper.json").read_text() + " ")
    with pytest.raises(ToothInstanceNetFixtureError, match="checksum"):
        load_validated_fixture(root, arch=ArchType.UPPER)


@pytest.mark.parametrize(
    "setup, message",
    [
        (lambda root: (root / "manifest.json").unlink(), "manifest"),
        (lambda root: (root / "upper.stl").unlink(), "checksum|upper.json or upper.stl"),
    ],
)
def test_missing_required_file_fails(tmp_path: Path, setup, message: str) -> None:
    root = _write_artifact(tmp_path / "artifact")
    setup(root)
    with pytest.raises(ToothInstanceNetFixtureError, match=message):
        load_validated_fixture(root, arch=ArchType.UPPER)


def test_json_length_mismatch_fails(tmp_path: Path) -> None:
    root = _write_artifact(tmp_path / "artifact")
    _rewrite_json(root, "upper.json", lambda payload: payload["labels"].pop())
    with pytest.raises(ToothInstanceNetFixtureError, match="cardinality"):
        load_validated_fixture(root, arch=ArchType.UPPER)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda payload: payload["instances"].__setitem__(0, 14), "instance IDs"),
        (lambda payload: payload["labels"].__setitem__(0, 99), "semantic labels"),
        (lambda payload: payload["labels"].__setitem__(0, 12), "exactly one semantic label"),
        (
            lambda payload: [payload["labels"].__setitem__(index, 16) for index in range(36, 42)],
            "missing an expected semantic label",
        ),
    ],
)
def test_invalid_per_vertex_semantics_fail(tmp_path: Path, mutate, message: str) -> None:
    root = _write_artifact(tmp_path / "artifact")
    _rewrite_json(root, "upper.json", mutate)
    with pytest.raises(ToothInstanceNetFixtureError, match=message):
        load_validated_fixture(root, arch=ArchType.UPPER)


def test_manifest_configuration_and_audit_are_required(tmp_path: Path) -> None:
    root = _write_artifact(tmp_path / "artifact")
    _rewrite_manifest(root, lambda manifest: manifest["configuration"].update(norm=False))
    with pytest.raises(ToothInstanceNetFixtureError, match="configuration"):
        load_validated_fixture(root, arch=ArchType.UPPER)

    root = _write_artifact(tmp_path / "artifact-2")
    _rewrite_manifest(
        root, lambda manifest: manifest["semantic_audit"][0].update(semantic_pass=False)
    )
    with pytest.raises(ToothInstanceNetFixtureError, match="semantic audit"):
        load_validated_fixture(root, arch=ArchType.UPPER)


def test_stl_topology_and_vertex_count_fail_closed(tmp_path: Path) -> None:
    root = _write_artifact(tmp_path / "artifact")
    stl = bytearray((root / "upper.stl").read_bytes())
    stl[80:84] = struct.pack("<I", 14)
    (root / "upper.stl").write_bytes(stl)
    _rewrite_checksums(root, "upper.stl")
    with pytest.raises(ToothInstanceNetFixtureError, match="topology size"):
        load_validated_fixture(root, arch=ArchType.UPPER)


def test_canonical_source_hash_is_an_artifact_gate(tmp_path: Path) -> None:
    """WP-01: when a source mesh is provided, its hash must match the verified artifact STL."""
    root = _write_artifact(tmp_path / "artifact")
    source = tmp_path / "canonical.stl"
    source.write_bytes(b"different serialization")
    with pytest.raises(ToothInstanceNetFixtureError, match="does not match verified artifact"):
        load_validated_fixture(root, arch=ArchType.UPPER, source_mesh_path=source)


def test_matching_source_hash_allows_fixture_load(tmp_path: Path) -> None:
    root = _write_artifact(tmp_path / "artifact")
    source = root / "upper.stl"
    result = load_validated_fixture(root, arch=ArchType.UPPER, source_mesh_path=source)
    assert result.segmentation.metadata.fixture is True


def test_no_synthetic_fallback(tmp_path: Path) -> None:
    with pytest.raises(ToothInstanceNetFixtureError, match="unavailable"):
        load_validated_fixture(tmp_path / "does-not-exist", arch=ArchType.UPPER)
