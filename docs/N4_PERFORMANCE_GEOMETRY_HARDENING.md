# N4 Performance & Geometry Hardening

Diagnostic-driven performance fixes for the two algorithmic bottlenecks proven by the
N3 diagnostic pass, plus live processing status, real-milestone progress, and observability.
No clinical/geometric semantics were changed; every fix is characterized before/after with
numeric evidence, and every accepted difference (none found) is documented.

## N3 baseline (recap)

The N3 diagnostic pass proved the "frozen at 70% / Elapsed 02:09" symptom was not a hang, a
crashed worker, or stopped polling. Two independent, real bottlenecks were found:

1. `adapters/toothinstancenet/fixture.py::load_validated_fixture` reconstructed each of the 14
   tooth instances using `vertex in vertex_indices` where `vertex_indices` was a plain `tuple`
   — an O(vertices) linear scan per face vertex, i.e. O(V×F) overall. Measured **~82–84s per
   arch** on the real validated artifact (`upper.stl`: 171,139 triangles, 86,401 unique
   vertices).
2. `engines/validation/geometric_engine.py::_mesh_pair_metrics` was a pure-Python nested loop
   over every triangle in mesh A against every triangle in mesh B (O(F1×F2)), only gated by a
   cheap AABB check per pair. On the real closest adjacent-tooth pair (6,419×6,871 faces) it
   did not finish within 300s.
3. `GET /cases/{id}/processing-status` returned the raw persisted status dict; `elapsed_seconds`
   was computed once at write time inside `_status()`, never recomputed on read — so while stuck
   inside `generate_plan()`, every poll returned an identical, frozen payload.

## N4.1 — Live processing status

**Root cause:** `elapsed_seconds` was a static value baked into the persisted job dict at the
moment of the last `_status()` write, not recomputed when the client polled.

**Fix:** `services/api/app/processing.py` now exposes `live_processing_status(case_id)`, which
recomputes `elapsed_seconds` from the persisted `started_at` on every read *only while the job is
`PROCESSING`*. Terminal jobs (`COMPLETED`/`FAILED`/`CANCELLED`) keep the elapsed value that was
persisted at the moment they became terminal — no retroactive changes to finished jobs.
`GET /cases/{case_id}/processing-status` (`services/api/app/routers/cases.py`) now calls this
accessor instead of returning the raw store value. The API contract (`ProcessingStatus` shape,
polling cadence) is unchanged; only the *value* of `elapsed_seconds` computation moved from
write-time to read-time for in-flight jobs.

**Tests:** `tests/python/test_processing_status_live.py` — proves elapsed increases across two
reads of a still-`PROCESSING` job with an older `started_at`, and that `COMPLETED`/`FAILED`
jobs return a stable value across repeated reads.

## N4.2 — Fixture reconstruction complexity

**Fix:** `vertex_indices` (still a `tuple`, so centroid summation order — and therefore the
exact floating-point result — is unchanged) is now also wrapped in a `frozenset` used only for
the `in` membership tests inside the per-face loop, turning an O(V) linear scan into an
O(1)-average hash lookup. No deduplication, reordering, or geometry simplification was
introduced; `triangle_indices`, `vertex_indices`, `mesh_faces`, and `centroid` are computed by
exactly the same formulas as before.

**Benchmark (real cached artifact, `official_real_case_stage2_verified_v1`):**

| Arch  | Triangles | Unique vertices | Before (N3) | After (N4.2) |
|-------|-----------|-----------------|-------------|--------------|
| upper | 171,139   | 86,401          | ~82–84s     | **1.5–1.9s** |
| lower | 139,048   | ~72,700         | (not separately timed in N3) | **1.5s**   |

**Correctness:** A direct instrumented comparison against the pre-fix algorithm (same
`_verify_checksums`/`_validate_manifest`/`_validate_arch` helpers, only the membership-test
structure differs) on the real artifact produced **byte-identical** `triangle_indices`,
`vertex_indices`, `mesh_faces`, and `centroid` for all 14 reconstructed instances — 0
mismatches. `tests/python/test_toothinstancenet_fixture_performance.py` codifies this as a
synthetic-artifact equivalence test plus a scale/timing regression guard (fails if
reconstruction regresses toward O(V×F)), and a deterministic instance-ordering test
(N4.5 item 3: `tooth_ref` stays `instance:0..13` in order).

## N4.3 — Replace O(F1×F2) triangle-pair validation

**Architecture implemented** (exactly the required 5 stages):

1. Whole-mesh AABB rejection — unchanged, still the first check in `_validate_stage`.
2. Spatial acceleration structure — `trimesh.Trimesh.triangles_tree`, an `rtree.index.Index`
   over per-triangle AABBs. `rtree` is already a runtime dependency of the project's existing
   `trimesh[easy]` extra (see **Dependencies** below) — nothing new was added.
3. Candidate triangle-pair generation — for each triangle in mesh A, its AABB (expanded by the
   broad-phase tolerance) is used to query mesh B's `triangles_tree.intersection(...)`, yielding
   only the candidate triangles whose AABB is within tolerance. Every candidate is re-confirmed
   with the *same* `_aabb_distance(...) > tolerance: continue` gate the original nested loop
   used, so the rtree result (a safe superset) can never admit a pair the old code would have
   rejected.
4. Narrow-phase — the exact same `_triangle_distance`/`_triangles_intersect` algebra (point-
   triangle, segment-segment, segment-triangle formulas), now evaluated as batched numpy
   operations (`_triangle_distance_batch`, `_triangles_intersect_batch`, etc.) across all
   candidate pairs at once instead of one Python function call per pair. The scalar functions
   are kept unchanged in the module as the semantic reference for equivalence tests.
5. Aggregation — minimum distance, intersects, and depth are computed from the batched results
   with the same reduction logic (`min`, `any`, bounding-box overlap depth) as before.

**Why both a broad-phase *and* a narrow-phase fix were required:** the rtree broad-phase alone
cut the real closest-adjacent-tooth-pair candidate count from ~44M (6,419×6,871) to ~73K, but
even 73K pure-Python narrow-phase calls (~1.37ms each, dominated by per-call numpy overhead)
would still take ~100s. Vectorizing the narrow-phase math removed that overhead.

**Benchmark (real cached artifact, single closest adjacent-tooth pair, 6,419×6,871 faces):**

| Stage | Before (N3) | After broad-phase only | After broad+narrow-phase (final) |
|---|---|---|---|
| Candidate pairs evaluated | 44,047,749 (all) | 73,297 | 73,297 |
| Wall time | did not finish in 300s | ~100s (estimated from per-candidate cost) | **2.45–2.49s** |

**Benchmark (one full real validation stage, 14 upper teeth, 91 combinations, 13 pass the AABB
prefilter):** **33.05s** total (down from an effectively unbounded/many-hours full cross-product
scan).

**Correctness — old vs new comparison, exactly as required:**

| Case | Old result | New result | Match |
|---|---|---|---|
| Clearly separated cubes | dist=9.0, intersects=False | same | ✅ (unit test) |
| Non-intersecting nearby cubes | dist=1.0, intersects=False | same | ✅ (unit test) |
| Touching cubes | dist=0.0, intersects=False | same | ✅ (unit test) |
| Intersecting cubes | intersects=True, depth=0.5 | same | ✅ (unit test) |
| Real adjacent tooth pair, 800×800-face subset | dist=0.17334768150337562, intersects=False, depth=0.0 (11.46s) | dist=0.17334768150337562, intersects=False, depth=0.0 (0.09s) | ✅ **bit-for-bit identical**, 127× faster |
| Real adjacent tooth pair, full mesh (6,419×6,871) | did not finish in 300s | dist=0.1732439932333547, intersects=False, depth=0.0 (2.49s) | consistent with the subset result (no old-algorithm value obtainable at full scale to diff against) |

No numerical tolerance had to be invoked — every comparison that could be run to completion
(cubes and the 800×800 real-geometry subset) was **exactly equal**, not merely "close". This is
expected: the fix only changes *which* pairs are visited and *how* the narrow-phase math is
batched, never the formulas themselves.

**Tests:** `tests/python/test_geometric_validation_performance.py` — parametrized equivalence
tests against a kept scalar reference implementation (separated / nearby-non-intersecting /
touching / intersecting cubes, plus denser icosphere meshes), a "no candidates within tolerance"
edge case, and a timing assertion that the vectorized path is strictly faster than the reference
on a moderately dense mesh pair.

## N4.4 — Intermediate real processing milestones

Milestones were added only at real, already-existing execution boundaries inside
`TreatmentSessionStore._compose()` (staging → validation → adjuncts), not fabricated from
elapsed time:

| Progress | Message | Real boundary |
|---|---|---|
| 70% | Preparing treatment setup | *(unchanged, existing)* — before `generate_plan` is called |
| 72% | Preparing geometric validation | proposal composed, about to stage |
| 82% | Evaluating collisions and proximity | staging complete, about to validate |
| 88% | Validating plan | *(unchanged, existing)* — geometric validation complete, entering the existing `VALIDATING_PLAN` stage |
| 96% | Finalizing workspace | *(unchanged, existing)* |
| 100% | Case ready | *(unchanged, existing)* |

An optional `progress_callback: Callable[[int, str], None] | None` parameter was threaded
through `generate_plan_with_progress` (a new internal function; the `POST /cases/{id}/plan`
FastAPI route itself keeps its original signature and schema — a `Callable` parameter cannot be
placed on a FastAPI route without breaking OpenAPI generation) → `TreatmentSessionStore.
create_from_treatment_input` → `_compose`. `services/api/app/processing.py`'s worker now passes
a callback that re-emits `_status()` with the same `current_stage="BUILDING_PLAN"` and
`completed`/`pending` lists as before — only `overall_progress`/`message` change — preserving
the existing `STAGES` tuple and stage-name contract exactly.

Elapsed time remains live throughout (via N4.1) independent of how many milestones fire.

## N4.5 — Performance regression tests

| # | Coverage | File |
|---|---|---|
| 1 | Fixture reconstruction complexity regression + geometry equivalence + tooth_ref ordering | `tests/python/test_toothinstancenet_fixture_performance.py` |
| 2 | `_mesh_pair_metrics` correctness (old vs new) + broad/narrow-phase scaling | `tests/python/test_geometric_validation_performance.py` |
| 3 | Semantic-only `tooth_ref` ordering | `tests/python/test_toothinstancenet_fixture_performance.py::test_reconstruction_preserves_deterministic_instance_ordering` |
| 4 | Processing status live elapsed time | `tests/python/test_processing_status_live.py` |
| 5 | Full planning on the validated real artifact | `tests/performance/test_real_case_planning_bench.py` (separated; not in `testpaths`) |

The heavy real-artifact benchmark lives in `tests/performance/`, outside the
`testpaths = ["tests/python"]` configured in `pyproject.toml`, so it never runs as part of the
normal fast suite (verified: `pytest --collect-only` still collects exactly the same 139 tests
with or without this directory present). It is skipped automatically if the real artifact is not
present at a known location, and can be run explicitly with `pytest tests/performance -q -s`.

## N4.6 — Observability

Structured `logger.info(...)` timing was added, following the existing
`EVENT_NAME key=value` convention already used in `processing.py`:

- `FIXTURE_RECONSTRUCTION_COMPLETED` (`adapters/toothinstancenet/fixture.py`) — arch, duration,
  vertex/face/instance counts.
- `TREATMENT_STAGING_COMPLETED` (`services/api/app/treatment_sessions.py`) — plan id, duration,
  stage count.
- `GEOMETRIC_VALIDATION_COMPLETED` (`services/api/app/treatment_sessions.py`) — plan id,
  duration, stage count, overall status.
- `GEOMETRIC_VALIDATION_STAGES_COMPLETED` (`engines/validation/geometric_engine.py`) — total
  validation duration and aggregate proximity/collision/contact counts.
- `GEOMETRIC_VALIDATION_STAGE_COMPLETED` (`engines/validation/geometric_engine.py`) — per-stage
  duration, pairs evaluated, and per-category (proximity/collision/contact) counts.
- `PLAN_BUILDING_STARTED`/`PLAN_BUILDING_COMPLETED` (`processing.py`) — already existed from N3;
  unchanged.

None of this is surfaced in the doctor-facing UI; `user_message` strings remain the short,
non-technical milestone text shown in `CaseLoadingOverlay`.

## Dependencies

**None added.** `rtree` (used via `trimesh.Trimesh.triangles_tree`) is already installed as
part of the project's existing `trimesh[easy]>=4.4` dependency declared in
`services/api/pyproject.toml`; N4.3 only uses a property already exposed by that already-approved
library, it does not introduce a new package or license obligation.

## Known limitations

- The rtree/vectorized `_mesh_pair_metrics` narrow-phase batch currently builds full numpy arrays
  for all candidate pairs of a call at once; for a pathological case with millions of true
  candidates this could use significant memory. Chunking the batch was not implemented since no
  realistic case in this pass required it.

## N5 — Investigation and fix of the "all 91 pairs close" limitation (2026-09-24)

The "Known limitations" section above originally reported that the real 14-tooth case's full
3-stage `generate_plan` stayed impractically slow because `_mesh_for_state` always used
`state.final_target_faces` regardless of stage index. Investigating that report properly found
**two separate things**, one a false alarm and one a real, separate, active bug:

**`_mesh_for_state` was not actually broken.** `source_faces` and `final_target_faces` are the
*same* array by construction on every path that builds a `TargetToothState`/`StageToothState`
today: `TreatmentPlanningEngine.generate_from_input` sets `source_faces=tooth.instance.mesh_faces`
and `target_faces=tooth.instance.mesh_faces` — literally the same object reference — and
`rebuild_proposal`/doctor edits only ever replace `target_vertices`, never `target_faces`.
Movement is a per-vertex rigid transform that never changes topology or vertex count (checked
explicitly in `_build_stage`). So using `final_target_faces` at any stage was always safe in
practice. To make the *intended* per-stage representation explicit and fail closed instead of
silently misbehaving if this invariant is ever broken in the future, `_mesh_for_state` now picks
the face array that matches which vertex source `state.vertices` actually equals (`source_faces`
at stage 0, `final_target_faces` at the final stage, and — for interpolated stages — requires
`source_faces == final_target_faces`, erroring with `"source/target face topology mismatch for
interpolated stage"` otherwise). This produces byte-identical output to before for every real
code path (proven: existing `test_geometric_validation_phase7.py`,
`test_treatment_staging_phase6.py`, `test_doctor_editing_phase9.py` and the N4 performance tests
all pass unchanged), and adds `tests/python/test_stage_geometry_and_validation_keying.py`'s
topology-mismatch tests as new fail-closed coverage.

**The real, active bug: `GeometricValidationEngine._validate_stage` keyed its per-tooth mesh
lookup by `state.tooth_number`.** In `semantic_only_experimental` planning mode — the mode used
for *every* real ToothInstanceNet case, since no clinical FDI identity is asserted —
`tooth_number` is `None` for all 14 teeth. `meshes = {state.tooth_number: _mesh_for_state(state)
for state in ordered_states}` therefore collapsed to a single dict entry (whichever tooth was
last in iteration order), and every one of the 91 tooth-pair combinations resolved
`meshes[first.tooth_number]` and `meshes[second.tooth_number]` to the **same mesh**, silently
comparing a tooth's mesh against **itself** instead of its real neighbor, 91 times per stage.
This is what actually produced the previously-reported "all 91 pairs pass the AABB filter" —
comparing a mesh's own bounds against itself trivially has zero distance — and it also explains
why the full pipeline was so slow: the largest real tooth (~13k faces) was being compared
against itself, which is at least as expensive as any genuine adjacent pair and happened for
every one of the 91 "pairs," not just the ~13 real adjacent ones. **This bug applied to all real
cases and made geometric collision/proximity validation vacuous (not merely slow) for every
report a doctor would have seen from the semantic-only-experimental path.**

**Fix:** `_validate_stage`'s mesh lookup is now keyed by `_state_sort_key(state)` — the same
tooth_number-with-tooth_ref-fallback key already used to order teeth deterministically elsewhere
in this file (`_state_sort_key`, `.detect()`), so it never collapses regardless of planning mode.

### Before/after measurements (real cached artifact, `official_real_case_stage2_verified_v1`)

| Measurement | Before (bug present) | After (fixed) |
|---|---|---|
| Close-pair count per stage (of 91 combinations) | 91 of 91 (every pair a self-comparison) | **13 of 91** (the real anatomically-adjacent pairs) |
| Geometric validation time per stage | did not finish in 120s in earlier ad hoc measurement | **~33.0–33.6s** |
| Intersections reported per stage | comparing a mesh to itself trivially — result depended on which tooth landed in the dict, not real anatomy | **0** (correct: untouched real arch has no genuine collisions) |
| Full 3-stage `generate_plan` (fixture load + planning + staging + validation) | did not finish in ~13 minutes in earlier measurement | **102–104s** |
| Stage 0 vs intermediate vs final geometry (moved tooth, translation_x=0.2 over 2 steps) | n/a | first-vertex x: `-20.850 → -20.750 → -20.650` — exact linear interpolation, confirms `_mesh_for_state`'s stage-0/final selection matches `source_vertices`/`final_target_vertices` exactly |
| Stage 0 vs intermediate vs final geometry (unmoved tooth) | n/a | vertices differ by ≤2.2e-16 (IEEE-754 double epsilon) across all 3 stages — floating-point noise from the existing (untouched) rigid-transform math, not a real geometric change |

Regression tests: `tests/python/test_stage_geometry_and_validation_keying.py` (6 tests — proves
the real bug is fixed with clearly-separated/intersecting semantic-only-mode teeth, proves
clinical_fdi and semantic-only modes agree on identical geometry, and proves the
`_mesh_for_state` topology-mismatch fail-closed behavior). Full fast suite:
`tests/python/test_toothinstancenet_fixture_performance.py`-plus-total is **144 passed, 1
deselected, ~15s** (up from 138 passed before this fix; 6 new tests, all green). The previously-
deselected `test_semantic_only_planning.py::test_semantic_only_planning_does_not_crash_on_missing_fdi`
now completes in **~100s** (previously effectively unbounded) and fails only because its own
premise is stale for the tracked artifact — the real artifact always has a populated `tooth_ref`,
so the "missing FDI" 400/409/503 branch it expects is never reached and planning legitimately
returns 200 OK; this is a pre-existing test-authoring issue unrelated to this fix and was left
untouched (out of scope for this pass).

### Real-case benchmark suite (`tests/performance`)

Added `test_real_artifact_full_three_stage_generate_plan_is_practical`, asserting each stage
reports strictly between 0 and 91 close pairs (catching a regression back to either the
self-comparison bug or a total AABB-filter failure) and that the full 3-stage plan stays under
180s. All 3 performance tests pass: fixture reconstruction ~1.5–3.0s/arch, closest real pair
~2.5s, full 3-stage `generate_plan` **103.60s** with `close_pairs=13` on every stage.

