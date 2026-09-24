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


def test_real_artifact_full_three_stage_generate_plan_is_practical(monkeypatch) -> None:
    """End-to-end: fixture load + planning + 3-stage staging + geometric validation.

    Proves the tooth_number-keying fix in `_validate_stage`: each stage must report the real
    ~13 anatomically-adjacent close pairs (never 0 and never 91-of-91, which would mean every
    tooth silently validated against itself).
    """
    root = _find_artifact_root()
    if root is None:
        pytest.skip("Validated real-case artifact is not available in this environment")

    monkeypatch.setenv("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
    monkeypatch.setenv("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(root))

    from app.toothinstancenet_configuration import load_validated_fixture_result
    from app.treatment_sessions import TreatmentSessionStore

    from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
    from domain.treatment_plan.setup import (
        ToothMovement,
        TreatmentObjective,
        TreatmentObjectiveType,
    )

    started = time.perf_counter()
    reviewed = load_validated_fixture_result(ArchType.UPPER)
    treatment_input = TreatmentPlanningInput.from_identification(
        reviewed.identification,
        diagnostics=(),
        planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL,
    )
    refs = [tooth.tooth_ref for tooth in reviewed.identification.teeth]
    objectives = (
        TreatmentObjective(
            "bench", TreatmentObjectiveType.ALIGNMENT, "bench",
            ((refs[0], ToothMovement(translation_x=0.2)),),
        ),
    )
    session = TreatmentSessionStore().create_from_treatment_input(
        "bench-case", treatment_input, objectives
    )
    elapsed = time.perf_counter() - started
    print(f"[bench] full 3-stage generate_plan: {elapsed:.2f}s", flush=True)
    for stage in session.validation.stage_results:
        close_pairs = len(stage.proximity_results)
        intersecting = sum(1 for item in stage.collision_results if item.intersects)
        contacts = sum(1 for item in stage.contact_results if item.is_contact)
        proximity_warnings = sum(
            1 for item in stage.proximity_results if item.status.value == "warning"
        )
        print(
            f"[bench] stage {stage.stage_index}: close_pairs={close_pairs} "
            f"intersections={intersecting} proximity_warnings={proximity_warnings} "
            f"contacts={contacts} status={stage.status.value}",
            flush=True,
        )
        # Real anatomy: ~13 anatomically-adjacent pairs, never 0 and never all 91 (which would
        # mean the tooth_number-keying bug regressed and every tooth is being compared to itself).
        assert 0 < close_pairs < 91
        assert intersecting == 0
    assert elapsed < 180.0, f"full 3-stage generate_plan regressed to {elapsed:.2f}s"


if __name__ == "__main__":
    test_real_artifact_fixture_reconstruction_is_practical()
    test_real_artifact_closest_tooth_pair_validation_is_practical()
