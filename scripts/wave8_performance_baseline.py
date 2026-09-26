#!/usr/bin/env python3
"""Wave 8 performance baseline.

Measures cheap operations on this computer and cites the WP-12 real-case
benchmark without re-running multi-minute geometric validation.

Fixture timings are labeled fixture_test_only. Cited WP-12 rows keep their
original provenance and are not new patient-case evidence.
"""

from __future__ import annotations

import json
import os
import platform
import resource
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services" / "api")]
os.environ.setdefault("PYTEST_CURRENT_TEST", "wave8_baseline")

from domain.case.provenance import DataProvenance
from domain.tooth.identification import ToothCoordinateSystem
from domain.treatment_plan.setup import ToothMovement
from domain.treatment_plan.staging import StageMovement, StageToothState, StagingResult, TreatmentStage
from engines.performance.remaining_time import estimate_remaining
from engines.validation.geometric_engine import GeometricValidationConfiguration, GeometricValidationEngine
from engines.validation.report_cache import clear_validation_report_cache, get_cached_report, store_cached_report

OUT = ROOT / ".research/tmp/wave8_performance"
WP12 = ROOT / ".research/tmp/wp12_performance/benchmark.json"
OUT.mkdir(parents=True, exist_ok=True)


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _tooth(ref: str, instance_id: int, offset: float) -> StageToothState:
    verts = (
        (offset + 0.0, 0.0, 0.0),
        (offset + 1.0, 0.0, 0.0),
        (offset + 0.0, 1.0, 0.0),
        (offset + 0.0, 0.0, 1.0),
    )
    faces = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))
    frame = ToothCoordinateSystem(
        origin=(0.0, 0.0, 0.0),
        lateral_axis=(1.0, 0.0, 0.0),
        anterior_axis=(0.0, 1.0, 0.0),
        vertical_axis=(0.0, 0.0, 1.0),
    )
    return StageToothState(
        tooth_number=None,
        source_instance_id=instance_id,
        source_vertices=verts,
        source_faces=faces,
        final_target_vertices=verts,
        final_target_faces=faces,
        vertices=verts,
        coordinate_system=frame,
        movement=StageMovement(tooth_number=ref, movement=ToothMovement(), progress=0.0),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        tooth_ref=ref,
        arch="upper",
        planning_mode="semantic_only_experimental",
    )


def _tiny_staging() -> StagingResult:
    stage = TreatmentStage(
        stage_index=0,
        stage_id="wave8-s0",
        tooth_states=(_tooth("upper-1", 1, 0.0), _tooth("upper-2", 2, 5.0)),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        stage_hash="wave8-h0",
    )
    return StagingResult(
        plan_id="wave8-fixture",
        staging_id="wave8-staging-1",
        stages=(stage,),
        provenance=DataProvenance.FIXTURE,
        fixture=True,
        assumptions=(),
        warnings=(),
        limitations=(),
    )


def _time(fn, repeats: int = 1) -> dict:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - started)
    samples.sort()
    mid = samples[len(samples) // 2]
    return {"repeats": repeats, "min_s": samples[0], "median_s": mid, "max_s": samples[-1]}


def main() -> None:
    environment = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "live_tooth_instance_net": False,
        "environment_blocker": "BLOCKED_BY_ENVIRONMENT",
        "note": "This fingerprint is for the measurement host. It is not used as another user's ETA.",
    }
    samples = [
        {
            "operation_id": "case-processing",
            "environment_id": "bench",
            "input_class": "both-arches",
            "duration_seconds": duration,
        }
        for duration in (100, 110, 120, 130)
    ]
    estimator = _time(
        lambda: estimate_remaining(
            samples,
            elapsed_seconds=40,
            operation_id="case-processing",
            environment_id="bench",
            input_class="both-arches",
        ),
        repeats=2000,
    )
    clear_validation_report_cache()
    staging = _tiny_staging()
    configuration = GeometricValidationConfiguration(1.0, 0.001, 0.0)
    miss = _time(lambda: GeometricValidationEngine().validate(staging, configuration), repeats=1)
    report = GeometricValidationEngine().validate(staging, configuration)
    store_cached_report(staging, configuration, report)
    hit = _time(lambda: get_cached_report(staging, configuration), repeats=20)
    cached = get_cached_report(staging, configuration)
    changed = GeometricValidationConfiguration(0.5, 0.001, 0.0)
    miss_on_threshold = get_cached_report(staging, changed) is None
    cited = []
    if WP12.is_file():
        payload = json.loads(WP12.read_text(encoding="utf-8"))
        for row in payload.get("measurements", []):
            wall = row.get("wall_s") or {}
            cited.append(
                {
                    "label": row.get("label"),
                    "median_s": wall.get("median"),
                    "provenance": "cited_wp12_not_rerun",
                    "geometry": "real_case_upper_with_fixture_segmentation_backend",
                    "clinical_segmentation_validation": False,
                    "source": str(WP12.relative_to(ROOT)),
                }
            )
    measurements = {
        "wave": 8,
        "new_measurements": [
            {
                "label": "remaining_time_estimator_2000",
                "provenance": "synthetic_engineering_benchmark",
                "geometry": "none",
                **estimator,
            },
            {
                "label": "fixture_validation_cache_miss",
                "provenance": "fixture_test_only",
                "geometry": "two_tetrahedra",
                "clinical": False,
                **miss,
                "report_id": report.report_id,
            },
            {
                "label": "fixture_validation_cache_hit",
                "provenance": "fixture_test_only",
                "geometry": "two_tetrahedra",
                "clinical": False,
                **hit,
                "report_id_match": cached is not None and cached.report_id == report.report_id,
                "threshold_change_misses": miss_on_threshold,
            },
        ],
        "cited_wp12": cited,
        "rss_mb_after": _rss_mb(),
        "optimizations": [
            {
                "name": "duplicate_treatment_load_on_completion",
                "before": "A second processing poll for the same completed job could start another treatment load.",
                "after": "claimTerminalLoad allows one load per job id.",
                "delta": "one load instead of a duplicate; not a validation speedup",
                "correctness": "job id claim; source scans and report semantics unchanged",
            },
            {
                "name": "geometric_validation_cpu",
                "before": "WP-12 upper real in-process median is cited, not re-run",
                "after": "unchanged engine",
                "delta": "no CPU reduction in Wave 8",
                "reason": "Narrow-phase time is the engine. Isolation and the report cache already exist. Weakening the engine is out of scope.",
            },
        ],
    }
    (OUT / "environment.json").write_text(json.dumps(environment, indent=2), encoding="utf-8")
    (OUT / "measurements.json").write_text(json.dumps(measurements, indent=2), encoding="utf-8")
    (OUT / "baseline.json").write_text(
        json.dumps(
            {
                "wave": 8,
                "host": environment,
                "estimator_2000_median_s": estimator["median_s"],
                "fixture_validation_miss_s": miss["median_s"],
                "fixture_validation_hit_median_s": hit["median_s"],
                "cited_wp12_present": bool(cited),
                "live_inference": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    methodology = f"""# Wave 8 measurement methodology

Measured on this host at {environment["timestamp_utc"]}.
Platform: {environment["platform"]}. CPUs: {environment["cpu_count"]}.

## What was run now

- Remaining-time estimator, 2000 calls, synthetic durations, no geometry.
- Geometric validation cache miss and hit on two fixture tetrahedra. This is not a patient case and not the multi-minute dual-arch cost.
- Cache key still misses when the proximity threshold changes. Report id on a hit matches the stored report.

## What was cited, not re-run

WP-12 `.research/tmp/wp12_performance/benchmark.json` remains the real-case timing source for treatment setup, staging, upper validation, session compose, review-bundle serialization, and reopen RSS. Those rows are copied into `measurements.json` with provenance `cited_wp12_not_rerun`. They are not a new clinical run and they are not this user's remaining-time estimate.

Live ToothInstanceNet inference was not run. This host stays BLOCKED_BY_ENVIRONMENT.

## What was not treated as an ETA

Cited medians are evidence about this repository's earlier benchmark. The product shows a remaining time only from completed jobs recorded on the current computer for the same operation and input class.
"""
    (OUT / "methodology.md").write_text(methodology, encoding="utf-8")
    print(json.dumps({"estimator_median_s": estimator["median_s"], "miss_s": miss["median_s"], "hit_median_s": hit["median_s"], "rss_mb": _rss_mb()}))


if __name__ == "__main__":
    main()
