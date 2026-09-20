from pathlib import Path

import trimesh

from engines.geometry.mesh_validation import MIN_TRIANGLE_COUNT, validate_mesh_file


def _write_box_stl(path: Path, subdivisions: int = 0) -> None:
    mesh = trimesh.creation.icosphere(subdivisions=subdivisions, radius=5.0)
    mesh.export(path)


def test_validate_missing_file(tmp_path: Path) -> None:
    result = validate_mesh_file(tmp_path / "missing.stl")
    assert not result.is_valid
    assert "not found" in result.errors[0].lower()


def test_validate_small_mesh_is_invalid(tmp_path: Path) -> None:
    stl_path = tmp_path / "tiny.stl"
    # icosphere lvl0 has 20 faces, below MIN_TRIANGLE_COUNT
    _write_box_stl(stl_path, subdivisions=0)
    result = validate_mesh_file(stl_path)
    assert result.triangle_count < MIN_TRIANGLE_COUNT
    assert not result.is_valid
    assert any("Triangle count" in e for e in result.errors)


def test_validate_large_mesh_is_valid(tmp_path: Path) -> None:
    stl_path = tmp_path / "large.stl"
    _write_box_stl(stl_path, subdivisions=4)  # icosphere lvl4 has thousands of faces
    result = validate_mesh_file(stl_path)
    assert result.triangle_count >= MIN_TRIANGLE_COUNT
    assert result.is_valid
    assert result.is_watertight
