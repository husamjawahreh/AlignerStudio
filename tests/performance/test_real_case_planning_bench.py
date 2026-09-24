"""Heavyweight real-artifact benchmark — NOT part of the fast unit-test suite.

`pyproject.toml` sets `testpaths = ["tests/python"]`, so this directory is never picked up by a
plain `pytest` invocation. Run it explicitly:

    pytest tests/performance -q -s

or directly as a script:

    python tests/performance/test_real_case_planning_bench.py

It exercises the real validated ToothInstanceNet artifact (`official_real_case_stage2_verified_v1`,
tracked in the repo) end to end: fixture reconstruction, treatment staging, and geometric
validation, reporting wall-clock timings for each stage. It is skipped automatically if the
artifact cannot be located.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from adapters.toothinstancenet.fixture import load_validated_fixture
from domain.tooth.identification import ArchType

_CANDIDATE_ARTIFACT_ROOTS = (
    Path("/tmp/alignerstudio-toothinstancenet-artifacts/official_real_case_stage2_verified_v1"),
    Path(__file__).resolve().parents[2] / ".research/tmp/official_real_case_stage2_verified_v1",
)


def _find_artifact_root() -> Path | None:
    env_dir = os.environ.get("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR")
    if env_dir and (Path(env_dir) / "manifest.json").is_file():
        return Path(env_dir)
    for candidate in _CANDIDATE_ARTIFACT_ROOTS:
        if (candidate / "manifest.json").is_file():
            return candidate
    return None


def test_real_artifact_fixture_reconstruction_is_practical() -> None:
    """N4.5.5: fixture reconstruction alone must stay well under a minute per arch."""
    root = _find_artifact_root()
    if root is None:
        pytest.skip("Validated real-case artifact is not available in this environment")

    for arch in (ArchType.UPPER, ArchType.LOWER):
        started = time.perf_counter()
        result = load_validated_fixture(root, arch=arch)
        elapsed = time.perf_counter() - started
        print(f"[bench] {arch.value} fixture reconstruction: {elapsed:.2f}s", flush=True)
        assert len(result.segmentation.instances) == 14
        # N3 baseline was ~82-84s per arch; N4.2 must keep this well under 10s.
        assert elapsed < 10.0, f"{arch.value} fixture reconstruction regressed to {elapsed:.2f}s"


def test_real_artifact_closest_tooth_pair_validation_is_practical() -> None:
    """N4.5.5: the single slowest real adjacent-tooth pair must stay well under a minute."""
    import itertools

    import numpy as np
    import trimesh

    from engines.validation.geometric_engine import _mesh_pair_metrics

    root = _find_artifact_root()
    if root is None:
        pytest.skip("Validated real-case artifact is not available in this environment")

    result = load_validated_fixture(root, arch=ArchType.UPPER)
    instances = result.segmentation.instances

    def centroid_distance(pair: tuple) -> float:
        first_centroid, second_centroid = np.array(pair[0].centroid), np.array(pair[1].centroid)
        return float(np.linalg.norm(first_centroid - second_centroid))

    closest = min(itertools.combinations(instances, 2), key=centroid_distance)
    first, second = closest

    def to_mesh(instance):
        return trimesh.Trimesh(
            vertices=np.array(instance.mesh_vertices),
            faces=np.array(instance.mesh_faces),
            process=False,
        )

    started = time.perf_counter()
    distance, intersects, depth = _mesh_pair_metrics(to_mesh(first), to_mesh(second), 1.0, 0.001)
    elapsed = time.perf_counter() - started
    print(
        f"[bench] closest real pair faces={len(first.mesh_faces)}x{len(second.mesh_faces)} "
        f"distance={distance:.4f} intersects={intersects} depth={depth:.4f} time={elapsed:.2f}s",
        flush=True,
    )
    # N3 baseline did not finish this single pair within 300s; N4.3 must keep it well under 30s.
    assert elapsed < 30.0, f"closest real pair validation regressed to {elapsed:.2f}s"


if __name__ == "__main__":
    test_real_artifact_fixture_reconstruction_is_practical()
    test_real_artifact_closest_tooth_pair_validation_is_practical()
