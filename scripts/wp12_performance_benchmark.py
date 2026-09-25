#!/usr/bin/env python3
"""WP-12 real-case performance benchmark — official_real_case_stage2_verified_v1.

Run (not part of the fast unit suite):

    .venv/bin/python scripts/wp12_performance_benchmark.py

Records cold/warm wall times and optional memory for the real dual-arch workflow
segments that can be driven without a live browser. Writes JSON evidence under
.research/tmp/wp12_performance/.

Does not invent numbers. Does not substitute fixtures for clinical output.
"""

from __future__ import annotations

import json
import os
import platform
import resource
import statistics
import sys
import tempfile
import threading
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services" / "api")]

os.environ.setdefault("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
os.environ.setdefault("ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND", "1")
ARTIFACT = ROOT / ".research/tmp/official_real_case_stage2_verified_v1"
os.environ.setdefault("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(ARTIFACT))
# Isolation on for the API-path probe; in-process path still measured separately.
os.environ.setdefault("ALIGNERSTUDIO_VALIDATION_PROCESS_ISOLATION", "1")
os.environ.setdefault("ALIGNERSTUDIO_VALIDATION_WORKERS", "1")

OUT_DIR = ROOT / ".research/tmp/wp12_performance"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _rss_mb() -> float:
    # Linux: ru_maxrss is kilobytes.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _measure(label: str, fn, *, repeats: int = 1) -> dict:
    samples: list[float] = []
    peak_py_mb: list[float] = []
    result = None
    for index in range(repeats):
        tracemalloc.start()
        t0 = time.perf_counter()
        result = fn()
        wall = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        samples.append(wall)
        peak_py_mb.append(peak / 1e6)
        print(
            f"  [{label}] run={index + 1}/{repeats} wall={wall:.3f}s "
            f"peak_py={peak / 1e6:.1f}MB rss={_rss_mb():.1f}MB",
            flush=True,
        )
    samples_sorted = sorted(samples)
    return {
        "label": label,
        "repeats": repeats,
        "wall_s": {
            "min": min(samples),
            "median": statistics.median(samples),
            "max": max(samples),
            "samples": samples,
        },
        "peak_python_alloc_mb": {
            "min": min(peak_py_mb),
            "median": statistics.median(peak_py_mb),
            "max": max(peak_py_mb),
        },
        "rss_mb_after": _rss_mb(),
        "result_summary": result if isinstance(result, (str, int, float, dict)) else None,
    }


def _environment() -> dict:
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "artifact": str(ARTIFACT),
        "artifact_exists": (ARTIFACT / "manifest.json").is_file(),
        "validation_process_isolation": os.environ.get(
            "ALIGNERSTUDIO_VALIDATION_PROCESS_ISOLATION", "1"
        ),
        "validation_workers": os.environ.get("ALIGNERSTUDIO_VALIDATION_WORKERS", "1"),
        "stage_count": os.environ.get("ALIGNERSTUDIO_STAGE_COUNT", "3"),
    }


def main() -> int:
    from adapters.toothinstancenet.fixture import ARTIFACT_ZIP_SHA256, load_validated_fixture
    from app.toothinstancenet_configuration import load_validated_fixture_result
    from app.treatment_sessions import TreatmentSessionStore, review_bundle
    from domain.tooth.identification import ArchType
    from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
    from domain.treatment_plan.setup import (
        ToothMovement,
        TreatmentObjective,
        TreatmentObjectiveType,
    )
    from domain.treatment_plan.staging import StagingConfiguration
    from engines.export.production_cad_engine import build_production_plan
    from engines.planning.setup_engine import TreatmentPlanningEngine
    from engines.planning.staging_engine import TreatmentStagingEngine
    from engines.validation.geometric_engine import (
        GeometricValidationConfiguration,
        GeometricValidationEngine,
    )
    from engines.validation.isolated_execution import (
        shutdown_validation_pool,
        validate_staging,
    )
    from engines.validation.report_cache import clear_validation_report_cache

    print("=== WP-12 REAL-CASE PERFORMANCE BENCHMARK ===", flush=True)
    env = _environment()
    print(json.dumps(env, indent=2), flush=True)
    if not env["artifact_exists"]:
        print("FAIL: official real-case artifact missing", flush=True)
        return 2

    clear_validation_report_cache()
    measurements: list[dict] = []

    # --- Fixture / segmentation reconstruction ---
    for arch in (ArchType.UPPER, ArchType.LOWER):
        measurements.append(
            _measure(
                f"fixture_load_{arch.value}_cold",
                lambda a=arch: {
                    "n": len(load_validated_fixture(ARTIFACT, arch=a).segmentation.instances)
                },
                repeats=1,
            )
        )
        measurements.append(
            _measure(
                f"fixture_load_{arch.value}_warm",
                lambda a=arch: {
                    "n": len(load_validated_fixture(ARTIFACT, arch=a).segmentation.instances)
                },
                repeats=1,
            )
        )

    upper = load_validated_fixture_result(ArchType.UPPER)
    lower = load_validated_fixture_result(ArchType.LOWER)
    assert len(upper.identification.teeth) == 14
    assert len(lower.identification.teeth) == 14

    # Upper-arch real teeth for bounded compose/validate; dual optional via env.
    treatment_input = TreatmentPlanningInput.from_identification(
        upper.identification,
        diagnostics=(),
        planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL,
    )
    refs = [tooth.tooth_ref for tooth in upper.identification.teeth]
    objectives = (
        TreatmentObjective(
            "wp12-bench",
            TreatmentObjectiveType.ALIGNMENT,
            "wp12 bench",
            ((refs[0], ToothMovement(translation_x=0.2)),),
        ),
    )

    # --- Setup ---
    def setup_once():
        proposal = TreatmentPlanningEngine().generate_from_input(
            "wp12-bench", treatment_input, objectives
        )
        tooth_n = (
            len(proposal.setup.target_states) if proposal.setup is not None else 0
        )
        return {"plan_id": proposal.plan_id, "teeth": tooth_n}

    measurements.append(_measure("treatment_setup", setup_once, repeats=3))
    proposal = TreatmentPlanningEngine().generate_from_input(
        "wp12-bench", treatment_input, objectives
    )

    # --- Staging ---
    stager = TreatmentStagingEngine()
    cfg = StagingConfiguration(stage_count=3, mode="macro")

    def stage_once():
        staging = stager.generate(proposal, cfg)
        return {
            "staging_id": staging.staging_id,
            "stages": len(staging.stages),
            "teeth_stage0": len(staging.stages[0].tooth_states),
        }

    measurements.append(_measure("staging", stage_once, repeats=3))
    staging = stager.generate(proposal, cfg)
    tooth_count = len(staging.stages[0].tooth_states)
    print(f"staging teeth={tooth_count} stages={len(staging.stages)}", flush=True)

    validation_cfg = GeometricValidationConfiguration(1.0, 0.001, 0.0)

    # --- Validation: one cold in-process + one isolated (equivalence) ---
    from dataclasses import replace as dc_replace

    # staging already upper-only from fixture identification above
    print("--- upper-arch geometric validation (in-process cold) ---", flush=True)

    def validate_upper_inprocess():
        report = GeometricValidationEngine().validate(staging, validation_cfg)
        return {
            "status": report.status.value,
            "report_id": report.report_id,
            "stages": len(report.stage_results),
            "proximity": sum(len(s.proximity_results) for s in report.stage_results),
            "collisions": sum(
                1 for s in report.stage_results for c in s.collision_results if c.intersects
            ),
        }

    measurements.append(
        _measure("validation_upper_inprocess_cold", validate_upper_inprocess, repeats=1)
    )
    inprocess_summary = measurements[-1]["result_summary"]

    print("--- upper-arch geometric validation (process-isolated) ---", flush=True)
    clear_validation_report_cache()

    def validate_upper_isolated():
        report = validate_staging(staging, validation_cfg)
        return {
            "status": report.status.value,
            "report_id": report.report_id,
            "stages": len(report.stage_results),
            "proximity": sum(len(s.proximity_results) for s in report.stage_results),
            "collisions": sum(
                1 for s in report.stage_results for c in s.collision_results if c.intersects
            ),
        }

    measurements.append(
        _measure("validation_upper_isolated", validate_upper_isolated, repeats=1)
    )
    isolated_summary = measurements[-1]["result_summary"]
    equivalence = {
        "report_id_match": (inprocess_summary or {}).get("report_id")
        == (isolated_summary or {}).get("report_id"),
        "status_match": (inprocess_summary or {}).get("status")
        == (isolated_summary or {}).get("status"),
        "inprocess": inprocess_summary,
        "isolated": isolated_summary,
    }
    print(f"equivalence: {equivalence}", flush=True)

    # Responsiveness: ticker must advance while isolated validate runs (reuse isolated path).
    # Use a short synthetic staging so the probe stays cheap; real-case isolation measured above.
    progress_ticks = {"n": 0}

    def _ticker():
        while not getattr(_ticker, "stop", False):
            progress_ticks["n"] += 1
            time.sleep(0.02)

    def responsiveness_probe():
        from domain.case.provenance import DataProvenance
        from domain.tooth.identification import ToothCoordinateSystem
        from domain.treatment_plan.setup import ToothMovement
        from domain.treatment_plan.staging import StageMovement, StageToothState, TreatmentStage

        verts = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        faces = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))
        frame = ToothCoordinateSystem(
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
        )

        def tiny(ref: str, iid: int, dx: float) -> StageToothState:
            shifted = tuple((x + dx, y, z) for x, y, z in verts)
            return StageToothState(
                tooth_number=None,
                source_instance_id=iid,
                source_vertices=shifted,
                source_faces=faces,
                final_target_vertices=shifted,
                final_target_faces=faces,
                vertices=shifted,
                coordinate_system=frame,
                movement=StageMovement(tooth_number=ref, movement=ToothMovement(), progress=0.0),
                provenance=DataProvenance.FIXTURE,
                fixture=True,
                tooth_ref=ref,
                arch="upper",
            )

        tiny_staging = dc_replace(
            staging,
            staging_id="wp12-responsive-probe",
            stages=(
                TreatmentStage(
                    0,
                    "s0",
                    (tiny("u1", 1, 0.0), tiny("u2", 2, 5.0)),
                    DataProvenance.FIXTURE,
                    True,
                    "h0",
                ),
            ),
        )
        progress_ticks["n"] = 0
        _ticker.stop = False  # type: ignore[attr-defined]
        thread = threading.Thread(target=_ticker, daemon=True)
        thread.start()
        t0 = time.perf_counter()
        report = validate_staging(tiny_staging, validation_cfg)
        wall = time.perf_counter() - t0
        time.sleep(0.05)
        _ticker.stop = True  # type: ignore[attr-defined]
        thread.join(timeout=2)
        return {
            "validation_wall_s": wall,
            "concurrent_ticks": progress_ticks["n"],
            "report_id": report.report_id,
            "responsive": progress_ticks["n"] >= 3,
        }

    print("--- parent-thread responsiveness during isolated validation ---", flush=True)
    measurements.append(_measure("validation_isolated_responsiveness", responsiveness_probe))

    # Dual-arch full validate — optional long run (set WP12_FULL_DUAL_VALIDATE=1).
    full_dual = os.environ.get("WP12_FULL_DUAL_VALIDATE", "0") == "1"
    dual_result = None
    if full_dual:
        print("--- FULL dual-arch validation (long) ---", flush=True)
        clear_validation_report_cache()
        # Build dual-arch staging from both arches via session store compose path.
        from app.routers.cases import _combined_fixture_identification

        identification, _diagnostics = _combined_fixture_identification()
        dual_input = TreatmentPlanningInput.from_identification(
            identification,
            diagnostics=(),
            planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL,
        )
        dual_refs = [t.tooth_ref for t in dual_input.teeth]
        dual_objectives = (
            TreatmentObjective(
                "wp12-dual",
                TreatmentObjectiveType.ALIGNMENT,
                "wp12 dual",
                ((dual_refs[0], ToothMovement(translation_x=0.2)),),
            ),
        )
        dual_proposal = TreatmentPlanningEngine().generate_from_input(
            "wp12-dual", dual_input, dual_objectives
        )
        dual_staging = stager.generate(dual_proposal, cfg)

        def validate_dual():
            report = validate_staging(dual_staging, validation_cfg)
            return {
                "status": report.status.value,
                "report_id": report.report_id,
                "teeth": len(dual_staging.stages[0].tooth_states),
                "stages": len(report.stage_results),
            }

        measurements.append(_measure("validation_dual_isolated", validate_dual, repeats=1))
        dual_result = measurements[-1]
    else:
        print(
            "SKIP full dual-arch validate (set WP12_FULL_DUAL_VALIDATE=1 to enable)",
            flush=True,
        )

    # --- Review bundle serialize (workspace transfer proxy) ---
    store = TreatmentSessionStore()
    # Force in-process for session compose speed in bench when cache cold;
    # uses isolation+cache path as production does.
    clear_validation_report_cache()
    session_dir = tempfile.mkdtemp(prefix="wp12-sessions-")
    os.environ["ALIGNERSTUDIO_TREATMENT_SESSION_DIR"] = session_dir
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(session_dir)

    def compose_session():
        # Use upper-only identification for bounded compose when dual is huge;
        # still exercises real fixture teeth.
        ti = TreatmentPlanningInput.from_identification(
            upper.identification,
            diagnostics=(),
            planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL,
        )
        urefs = [t.tooth_ref for t in upper.identification.teeth]
        objs = (
            TreatmentObjective(
                "wp12",
                TreatmentObjectiveType.ALIGNMENT,
                "wp12",
                ((urefs[0], ToothMovement(translation_x=0.2)),),
            ),
        )
        sess = store.create_from_treatment_input("wp12-case", ti, objs)
        return {
            "source_kind": sess.source_kind,
            "teeth": len(sess.staging.stages[0].tooth_states),
            "validation": sess.validation.status.value,
            "report_id": sess.validation.report_id,
        }

    print("--- treatment session compose (upper real case) ---", flush=True)
    measurements.append(_measure("session_compose_upper", compose_session, repeats=1))
    # Warm cache path
    measurements.append(_measure("session_compose_upper_cached", compose_session, repeats=1))

    session = store.get("wp12-case")

    def serialize_review():
        bundle = review_bundle(session)
        stages = bundle.get("stages") or bundle.get("treatment", {}).get("stages") or []
        # Count teeth in first stage if present
        tooth_n = 0
        if stages:
            first = stages[0]
            tooth_n = len(first.get("teeth") or first.get("tooth_meshes") or [])
        payload = json.dumps(bundle)
        return {"json_bytes": len(payload), "stage_teeth": tooth_n}

    measurements.append(_measure("review_bundle_serialize", serialize_review, repeats=3))

    # --- Production CAD (if session supports it) ---
    try:
        from engines.export.production_cad_engine import ProductionCadEngine

        def production_once():
            # Prefer session-bound builder if available via store helpers later;
            # direct engine call with proposal/staging when API allows.
            plan = build_production_plan  # type: ignore
            return {"callable": callable(plan)}

        measurements.append(
            {
                "label": "production_cad_note",
                "note": "See scripts/wp10_production_cad_tech_benchmark.py for CAD timings; "
                "WP-12 does not re-run full export CAD unless session APIs are exercised.",
            }
        )
    except Exception as exc:
        measurements.append({"label": "production_cad_skip", "error": str(exc)})

    # Memory reopen probe: compose twice and compare RSS growth.
    rss_before = _rss_mb()
    compose_session()
    compose_session()
    rss_after = _rss_mb()
    memory = {
        "rss_before_reopen_mb": rss_before,
        "rss_after_two_reopens_mb": rss_after,
        "delta_mb": rss_after - rss_before,
    }
    print(f"memory reopen: {memory}", flush=True)

    shutdown_validation_pool()

    evidence = {
        "work_package": "WP-12",
        "artifact_id": "official_real_case_stage2_verified_v1",
        "artifact_zip_sha256": ARTIFACT_ZIP_SHA256,
        "environment": env,
        "equivalence_isolated_vs_inprocess": equivalence,
        "full_dual_validate_enabled": full_dual,
        "dual_result": dual_result,
        "memory_reopen": memory,
        "measurements": measurements,
        "wp13_and_later_started": False,
    }
    out_path = OUT_DIR / "benchmark.json"
    out_path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"Wrote {out_path}", flush=True)
    return 0 if equivalence["report_id_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
