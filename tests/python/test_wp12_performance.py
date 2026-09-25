"""WP-12 — validation process isolation and report-cache correctness."""

from __future__ import annotations

import threading
import time

import pytest

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ToothCoordinateSystem
from domain.treatment_plan.setup import ToothMovement
from domain.treatment_plan.staging import (
    StageMovement,
    StageToothState,
    StagingResult,
    TreatmentStage,
)
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)
from engines.validation.isolated_execution import (
    shutdown_validation_pool,
    validate_staging,
)
from engines.validation.report_cache import (
    clear_validation_report_cache,
    get_cached_report,
    store_cached_report,
)


def _frame() -> ToothCoordinateSystem:
    return ToothCoordinateSystem(
        origin=(0.0, 0.0, 0.0),
        lateral_axis=(1.0, 0.0, 0.0),
        anterior_axis=(0.0, 1.0, 0.0),
        vertical_axis=(0.0, 0.0, 1.0),
    )


def _tooth(ref: str, instance_id: int, offset: float) -> StageToothState:
    verts = (
        (offset + 0.0, 0.0, 0.0),
        (offset + 1.0, 0.0, 0.0),
        (offset + 0.0, 1.0, 0.0),
        (offset + 0.0, 0.0, 1.0),
    )
    faces = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))
    return StageToothState(
        tooth_number=None,
        source_instance_id=instance_id,
        source_vertices=verts,
        source_faces=faces,
        final_target_vertices=verts,
        final_target_faces=faces,
        vertices=verts,
        coordinate_system=_frame(),
        movement=StageMovement(tooth_number=ref, movement=ToothMovement(), progress=0.0),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        tooth_ref=ref,
        arch="upper",
        planning_mode="semantic_only_experimental",
    )


def _tiny_staging() -> StagingResult:
    """Minimal two-tooth stage for fast isolation/cache tests (not real-case timing)."""
    stage = TreatmentStage(
        stage_index=0,
        stage_id="s0",
        tooth_states=(_tooth("upper-1", 1, 0.0), _tooth("upper-2", 2, 5.0)),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        stage_hash="h0",
    )
    return StagingResult(
        plan_id="wp12-iso",
        staging_id="staging-wp12-iso-1",
        stages=(stage,),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        assumptions=(),
        warnings=(),
        limitations=(),
    )


@pytest.fixture(autouse=True)
def _clean_isolation(monkeypatch):
    clear_validation_report_cache()
    monkeypatch.setenv("ALIGNERSTUDIO_VALIDATION_PROCESS_ISOLATION", "1")
    yield
    clear_validation_report_cache()
    shutdown_validation_pool()


def test_isolated_validation_matches_inprocess_report_id(monkeypatch) -> None:
    monkeypatch.setenv("ALIGNERSTUDIO_VALIDATION_PROCESS_ISOLATION", "0")
    staging = _tiny_staging()
    cfg = GeometricValidationConfiguration(1.0, 0.001, 0.0)
    inprocess = GeometricValidationEngine().validate(staging, cfg)
    monkeypatch.setenv("ALIGNERSTUDIO_VALIDATION_PROCESS_ISOLATION", "1")
    shutdown_validation_pool()
    isolated = validate_staging(staging, cfg)
    assert isolated.report_id == inprocess.report_id
    assert isolated.status == inprocess.status
    assert len(isolated.stage_results) == len(inprocess.stage_results)
    for left, right in zip(isolated.stage_results, inprocess.stage_results):
        assert left.status == right.status
        assert len(left.collision_results) == len(right.collision_results)
        assert len(left.proximity_results) == len(right.proximity_results)


def test_report_cache_hit_same_staging_id() -> None:
    staging = _tiny_staging()
    cfg = GeometricValidationConfiguration(1.0, 0.001, 0.0)
    report = GeometricValidationEngine().validate(staging, cfg)
    assert get_cached_report(staging, cfg) is None
    store_cached_report(staging, cfg, report)
    hit = get_cached_report(staging, cfg)
    assert hit is not None
    assert hit.report_id == report.report_id


def test_report_cache_miss_on_threshold_change() -> None:
    staging = _tiny_staging()
    cfg_a = GeometricValidationConfiguration(1.0, 0.001, 0.0)
    cfg_b = GeometricValidationConfiguration(0.5, 0.001, 0.0)
    report = GeometricValidationEngine().validate(staging, cfg_a)
    store_cached_report(staging, cfg_a, report)
    assert get_cached_report(staging, cfg_b) is None


def test_isolated_validation_allows_concurrent_python_progress(monkeypatch) -> None:
    """While process-isolated validate runs, sibling threads in the parent must progress."""
    monkeypatch.setenv("ALIGNERSTUDIO_VALIDATION_PROCESS_ISOLATION", "1")
    staging = _tiny_staging()
    cfg = GeometricValidationConfiguration(1.0, 0.001, 0.0)
    ticks = {"n": 0}
    stop = threading.Event()

    def ticker() -> None:
        while not stop.is_set():
            ticks["n"] += 1
            time.sleep(0.01)

    thread = threading.Thread(target=ticker, daemon=True)
    thread.start()
    validate_staging(staging, cfg)
    time.sleep(0.05)
    stop.set()
    thread.join(timeout=2)
    assert ticks["n"] >= 3
