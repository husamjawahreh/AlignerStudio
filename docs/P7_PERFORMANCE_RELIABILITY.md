# P7 — Performance, Reliability & Scale

Evidence-driven pass against `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md` §11.
No clinical or production acceptance is claimed.

## Measured bottlenecks (before)

Representative artifact: `official_real_case_stage2_verified_v1` upper arch
(14 instances, dense crown meshes). Machine: local Linux, 12 CPUs.

| Workload | Before (this pass) | Notes |
|---|---|---|
| Warm fixture reconstruction / arch | 1.5–1.8s | Already N4.2-hardened; cold first extract ~12–16s |
| Staging (3 stages) | 0.61s | Not the bottleneck |
| Geometric validation / stage (serial) | 54.9 / 54.5 / 59.9s | 13 close pairs each; N4.3 narrow-phase still dominant |
| Full 3-stage validate (serial, no cache) | **~169.4s** | Sum of per-stage timings |
| Planning-intelligence alternatives | up to ~5× validate | Deferred for `validated_real_case` compose (P6 fix) |
| Viewer raycast | pointer-up only, ~14 meshes | Not measured as interactive bottleneck; `three-mesh-bvh` **not** adopted |
| Manifold3D / WASM | — | No boolean workload justifying adoption |

## Optimizations implemented

1. **Unmoved vertex identity reuse** (`engines/planning/staging_engine.py`)  
   When source == target (or stage 0), reuse the same vertex tuple object across stages.
2. **Deterministic cross-stage pair-metric cache** (`engines/validation/geometric_engine.py`)  
   Cache keyed by `(id(vertices_a), id(vertices_b))`. Only hits when geometry objects are
   identical — never suppresses findings, never weakens thresholds.
3. **Optional worker pool for close-pair narrow-phase** (`ALIGNERSTUDIO_VALIDATION_WORKERS`)  
   Default **1** after measured hang/regression with concurrent trimesh/rtree on dense real
   pairs. Engineering-fixture parallel vs serial parity remains tested when opted in.
4. **Lazy planning intelligence preserved** for `validated_real_case` compose; on-demand via
   `ensure_planning_intelligence`.
5. **Viewer geometry packing** without `flatMap` intermediates (`apps/web/src/viewer/geometryBuffers.ts`).
6. **Durable treatment-session checkpoints** + browser `sessionStorage` case rehydrate.
## After benchmarks (same real upper case)

Quiet-machine full validate with workers=1 + pair cache (`/tmp/p7_after_only.txt`):

| Workload | After | Notes |
|---|---|---|
| Unmoved vertex identity reuse stage0→1 | **4 / 14** teeth | Staging reuses tuple objects when source==target |
| Stage 0 / 1 / 2 validate | **83.1 / 69.0 / 69.0 s** | 13 close pairs, 0 intersections each |
| Full 3-stage validate | **221.1 s** (peak Python alloc **75.2 MB**) | `cache_hits=2`, `cache_misses=37` |
| Correctness | 13 close / 0 intersects / status=warning | Same finding pattern as before |

Interpretation (honest): on this one-tooth 0.2 mm movement plan, almost every close pair
still involves moved geometry, so the identity cache barely fires. Wall time is in the same
band as the serial baseline (~169 s before; ~221 s after on a warmer/longer run — do **not**
treat the delta as a claimed speedup). The cache remains correctness-safe and helps when more
teeth are truly unmoved; it does not replace N4 narrow-phase work.

Worker pools default **off** (`ALIGNERSTUDIO_VALIDATION_WORKERS=1`): concurrent trimesh/rtree
queries on dense real pairs hung/regressed (>4 min). Opt-in only after re-benchmarking.
Engineering-fixture parallel vs serial parity remains tested.

### Larger measured win: planning-intelligence laziness

Assisted alternatives still cost up to ~5× full validate when expanded. Compose for
`validated_real_case` keeps `generate_alternatives=False` (verified by P7 unit test). That
prevents the P6 real-case compose regression from returning.

## Reliability improvements

| Requirement | Implementation |
|---|---|
| Case recovery / backend restart | Existing `PROCESS_RESTARTED` on CaseStore load + tests |
| Duplicate job protection | Same-case `PROCESSING` returns existing `job_id` + tests |
| Stale job recovery | Startup recovery test |
| Interrupted processing | Unchanged: mark FAILED, user restarts analysis |
| Treatment session across API restart | Gzip+pickle checkpoints in `ALIGNERSTUDIO_TREATMENT_SESSION_DIR` |
| Browser refresh | `sessionStorage` active case id + rehydrate case/treatment |
| Repeated exports | Stability test on engineering demo |
| Large / dense meshes | Real-artifact benches + existing N4 guards |
| Repeated edits | Edit path keeps intelligence lazy for real cases |

## Tools explicitly not adopted (no measured justification)

- `three-mesh-bvh` — picking is pointer-up against ~14 tooth meshes
- Transferable buffers / WASM workers — review DTO still main-thread; no measured transfer cliff
- Manifold3D — no production boolean/repair workload in P7 scope

## Files

- `engines/validation/geometric_engine.py`
- `engines/planning/staging_engine.py`
- `services/api/app/session_persistence.py`
- `services/api/app/treatment_sessions.py`
- `services/api/app/config.py`
- `apps/web/src/caseWorkspacePersistence.ts`
- `apps/web/src/app/App.tsx`
- `apps/web/src/viewer/geometryBuffers.ts`
- `apps/web/src/viewer/StageViewer.tsx`
- `tests/python/test_p7_performance_reliability.py`
- `tests/python/conftest.py`
- `tests/performance/p7_baseline_measure.py`

## Known limitations

- Pair cache only helps unmoved geometry; a tooth that moves still recomputes adjacent pairs.
- Session checkpoints are large (full staged meshes); durable but not compact.
- Multi-process API deploy still needs an external lock for duplicate jobs (in-process only).
- Cold fixture ZIP extract remains slower than warm reconstruction.
- No P8 packaging / clean-machine acceptance in this phase.
