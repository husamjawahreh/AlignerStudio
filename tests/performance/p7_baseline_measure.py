"""P7 baseline measurements — run explicitly, not part of the fast suite.

    .venv/bin/python tests/performance/p7_baseline_measure.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "services" / "api")]

os.environ.setdefault("ALIGNERSTUDIO_SEGMENTATION_BACKEND", "toothinstancenet_fixture")
ARTIFACT = ROOT / ".research/tmp/official_real_case_stage2_verified_v1"
os.environ.setdefault("ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR", str(ARTIFACT))


def main() -> None:
    from domain.tooth.identification import ArchType
    from adapters.toothinstancenet.fixture import load_validated_fixture
    from app.toothinstancenet_configuration import load_validated_fixture_result
    from app.treatment_sessions import TreatmentSessionStore, review_bundle
    from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
    from domain.treatment_plan.setup import (
        ToothMovement,
        TreatmentObjective,
        TreatmentObjectiveType,
    )
    from domain.treatment_plan.staging import StagingConfiguration
    from engines.planning.intelligence import AdvancedPlanningIntelligenceEngine
    from engines.planning.setup_engine import TreatmentPlanningEngine
    from engines.planning.staging_engine import TreatmentStagingEngine
    from engines.validation.geometric_engine import (
        GeometricValidationConfiguration,
        GeometricValidationEngine,
    )

    print("=== P7 BASELINE ===", flush=True)
    for arch in (ArchType.UPPER, ArchType.LOWER):
        tracemalloc.start()
        t0 = time.perf_counter()
        result = load_validated_fixture(ARTIFACT, arch=arch)
        elapsed = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(
            f"fixture {arch.value}: {elapsed:.3f}s peak_py={peak / 1e6:.1f}MB "
            f"n={len(result.segmentation.instances)}",
            flush=True,
        )

    reviewed = load_validated_fixture_result(ArchType.UPPER)
    treatment_input = TreatmentPlanningInput.from_identification(
        reviewed.identification,
        diagnostics=(),
        planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL,
    )
    refs = [tooth.tooth_ref for tooth in reviewed.identification.teeth]
    objectives = (
        TreatmentObjective(
            "bench",
            TreatmentObjectiveType.ALIGNMENT,
            "bench",
            ((refs[0], ToothMovement(translation_x=0.2)),),
        ),
    )
    proposal = TreatmentPlanningEngine().generate_from_input(
        "bench-p7", treatment_input, objectives
    )
    print("proposal ok", flush=True)

    stager = TreatmentStagingEngine()
    t0 = time.perf_counter()
    staging = stager.generate(proposal, StagingConfiguration(stage_count=3, mode="macro"))
    print(f"staging: {time.perf_counter() - t0:.3f}s stages={len(staging.stages)}", flush=True)

    validator = GeometricValidationEngine()
    cfg = GeometricValidationConfiguration(1.0, 0.001, 0.0)
    for stage in staging.stages:
        t0 = time.perf_counter()
        stage_result = validator._validate_stage(stage, staging.provenance, cfg)
        close = len(stage_result.proximity_results)
        hits = sum(1 for item in stage_result.collision_results if item.intersects)
        print(
            f"  validate stage {stage.stage_index}: {time.perf_counter() - t0:.3f}s "
            f"close={close} intersects={hits}",
            flush=True,
        )
    t0 = time.perf_counter()
    report = validator.validate(staging, cfg)
    print(f"full validate: {time.perf_counter() - t0:.3f}s status={report.status.value}", flush=True)

    intel = AdvancedPlanningIntelligenceEngine(
        planner=TreatmentPlanningEngine(),
        stager=stager,
        validator=validator,
        validation_config=cfg,
    )
    t0 = time.perf_counter()
    lazy = intel.generate(
        proposal,
        staging,
        report,
        staging_configuration=StagingConfiguration(stage_count=3, mode="macro"),
        generate_alternatives=False,
    )
    print(f"intel lazy: {time.perf_counter() - t0:.3f}s n={len(lazy.candidates)}", flush=True)

    store = TreatmentSessionStore()
    tracemalloc.start()
    t0 = time.perf_counter()
    session = store.create_from_treatment_input("bench-p7", treatment_input, objectives)
    compose_dt = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(
        f"compose lazy: {compose_dt:.3f}s peak_py={peak / 1e6:.1f}MB "
        f"candidates={len(session.intelligence.candidates) if session.intelligence else 0} "
        f"source={session.source_kind}",
        flush=True,
    )

    t0 = time.perf_counter()
    bundle = review_bundle(session)
    payload = json.dumps(bundle)
    print(f"review_bundle: {time.perf_counter() - t0:.3f}s bytes={len(payload):,}", flush=True)

    t0 = time.perf_counter()
    expanded = store.ensure_planning_intelligence("bench-p7")
    print(
        f"ensure_intel: {time.perf_counter() - t0:.3f}s "
        f"n={len(expanded.intelligence.candidates)}",
        flush=True,
    )

    store2 = TreatmentSessionStore()
    store2.create_from_treatment_input("bench-edit", treatment_input, objectives)
    t0 = time.perf_counter()
    edited = store2.apply_edit("bench-edit", refs[0], {"translation_x": 0.3})
    print(
        f"apply_edit: {time.perf_counter() - t0:.3f}s "
        f"n={len(edited.intelligence.candidates) if edited.intelligence else 0}",
        flush=True,
    )

    td = Path(tempfile.mkdtemp())
    t0 = time.perf_counter()
    package = store2.export("bench-edit", td / "export")
    print(
        f"export: {time.perf_counter() - t0:.3f}s size={package.archive_path.stat().st_size:,}",
        flush=True,
    )
    t0 = time.perf_counter()
    for index in range(3):
        store2.export("bench-edit", td / f"export-{index}")
    print(f"export x3: {time.perf_counter() - t0:.3f}s", flush=True)


if __name__ == "__main__":
    main()
