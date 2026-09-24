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

- **A separate, pre-existing geometry-composition issue was discovered while benchmarking the
  full 3-stage plan for the real 14-tooth case, and is *not* fixed by N4.** `_mesh_for_state`
  (`engines/validation/geometric_engine.py`) always reads `state.final_target_faces` regardless
  of stage index, while `state.vertices` varies per stage (source / interpolated / target).
  When the real segmented tooth geometry flows through `TreatmentPlanningEngine.
  generate_from_input` + `TreatmentStagingEngine.generate`, this combination causes **all 91**
  tooth-pair combinations to pass the coarse whole-mesh AABB broad-phase filter in every stage
  (verified directly: `close_pairs=91` of 91, in all 3 stages), instead of the ~13
  anatomically-adjacent pairs seen when validating the raw fixture geometry directly. This
  inflates the real end-to-end `generate_plan` duration for the tracked real artifact well
  beyond the per-pair numbers above (full 3-stage compose did not finish in ~13 minutes in this
  environment). N4.2 and N4.3 are each independently proven correct and dramatically faster in
  isolation (single real pair: unbounded/>300s → 2.5s; one anatomically-correct 91-pair stage:
  unbounded → 33s); this remaining slowness is a different, deeper bug in how planning/staging
  composes per-stage vertex/face pairs, not a regression introduced by N4, and requires its own
  dedicated investigation before touching (per the strict "do not change clinical/geometric
  semantics" instruction for this pass).
- `tests/python/test_semantic_only_planning.py::test_semantic_only_planning_does_not_crash_on_missing_fdi`
  exercises the real tracked artifact end-to-end and is affected by the limitation above; it was
  already effectively impractical before N4 (old fixture load alone was ~82s, combined with an
  O(F1×F2) brute-force validation over pairs that were *also* already miscounted as 91-of-91
  close). It is not part of the fast test loop in this report (deselected) and should be
  re-classified as a slow/integration test once the composition issue above is fixed.
- The rtree/vectorized `_mesh_pair_metrics` narrow-phase batch currently builds full numpy arrays
  for all candidate pairs of a call at once; for a pathological case with millions of true
  candidates (e.g. if the composition issue above is fixed and still produces very large contact
  areas) this could use significant memory. Chunking the batch was not implemented since no
  realistic case in this pass required it once the composition issue is set aside.
