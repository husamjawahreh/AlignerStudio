# WP-12 — Performance Engineering

**Work package:** FIRST VERSION WP-12  
**Date:** 2026-09-25  
**Authoritative roadmap:** `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md` §11 (P7), `Aligner_Studio_First_Version_World_Class_Plan.md` WP-12  
**Baselines:** WP-01…WP-11 docs, `docs/P7_PERFORMANCE_RELIABILITY.md`, `docs/WP11_WORLD_CLASS_UX.md`  
**Scope:** Performance measurement and optimization only.  
**Explicit stop:** **WP-13 and all later work packages were NOT started.**

---

## 1. Verdict

**PASS WITH BLOCKER** (same GPU/runtime blocker as prior WPs for live ToothInstanceNet inference; full dual-arch geometric validation wall time remains multi-minute and was not shortened to interactive length in this WP).

What WP-12 achieved with evidence:

- Real-case performance audited on `official_real_case_stage2_verified_v1`.
- Geometric validation **process isolation** so long narrow-phase work no longer starves API/status handlers (primary WP-11 event-loop finding).
- Validation report **equivalence** preserved (`report_id` identical in-process vs isolated).
- Provenance-keyed **validation report cache** and **fixture reconstruction cache**.
- Single-pass fixture mesh reconstruction (order-preserving, WP-01 green).
- StageViewer **visibility/wireframe/isolate** no longer tears down BufferGeometry + BVH.
- Before/after measurements recorded under `.research/tmp/wp12_performance/`.
- Frontend tests, typecheck, lint, production build pass; WP-01…WP-10 backend regressions pass.

This is **not** doctor-ready, production-ready, or a claim that validation is “fast.” Dual-arch compose can still take many minutes of CPU; isolation makes the API remain responsive while that work runs.

---

## 2. Performance audit

Workflow profiled (real artifact, fixture segmentation backend — not synthetic clinical fixtures as primary evidence):

Launch → Case Intake → upload/bind → segmentation (validated artifact) → analysis/compose → workspace (`review_bundle`) → Treatment Setup → Staging → Refinement path (edit/recompose) → Validation → Production/Export (referenced WP-10 benches; not re-litigated).

Script: `scripts/wp12_performance_benchmark.py`  
Evidence: `.research/tmp/wp12_performance/benchmark.json`

---

## 3. Baseline environment

| Item | Value |
|---|---|
| Timestamp (UTC) | 2026-09-25T15:27:51Z |
| OS | Linux 7.0.0-31-generic x86_64 (glibc 2.39) |
| CPUs | 12 |
| RAM | 15 GiB |
| Python | 3.12.3 |
| Artifact | `.research/tmp/official_real_case_stage2_verified_v1` |
| Artifact ZIP SHA-256 | `b0f57d45e19ec1c981964dcad1309570fdc96ec21052ada62050fa3ccb8621b2` |
| Isolation default | `ALIGNERSTUDIO_VALIDATION_PROCESS_ISOLATION=1` |
| Validation workers | `ALIGNERSTUDIO_VALIDATION_WORKERS=1` (unchanged; thread pool still opt-in only) |

---

## 4. Baseline measurements (BEFORE optimizations)

From the WP-12 audit pass (tracemalloc-on wall samples) and prior WP-11/P7 evidence:

| Workload | Before | Source |
|---|---|---|
| Fixture reconstruct upper (warm, pre-single-pass) | ~11.2–13.9 s | WP-12 audit first run |
| Fixture reconstruct (P7 documented) | 1.5–1.8 s warm | `docs/P7_PERFORMANCE_RELIABILITY.md` |
| Real workspace load+serialize (WP-03) | ~3407.7 ms | `docs/WP03_WORLD_CLASS_3D_WORKSPACE.md` |
| Upper 3-stage geometric validate | ~169–221 s (P7); WP-12 cold **214.5 s** | P7 + WP-12 bench |
| Dual-arch live compose validation | ~18 minutes observed | `docs/WP11_WORLD_CLASS_UX.md` |
| StageViewer arch/wireframe toggle | Full scene + BVH rebuild | StageViewer deps audit |
| API status during validation | Stalled (GIL / sync handlers) | WP-11 browser QA |

---

## 5. Bottlenecks (evidence)

1. **GeometricValidationEngine narrow-phase** (`engines/validation/geometric_engine.py`) — dominant CPU; Python rtree candidate loop + triangle batch metrics per close pair × stages.
2. **In-process validate during processing** — CPU-bound work shared the API process GIL with sync FastAPI routes → status/health starvation (WP-11).
3. **Fixture reconstruction** — previously O(instances × faces) face scans; checksum + STL/JSON parse also costly on cold process.
4. **`review_bundle` JSON** — ~16.6 MB for upper 14-tooth session; serialize median ~6.6 s in bench (transfer cliff).
5. **StageViewer full rebuild** — arch filter / isolate / wireframe previously disposed and rebuilt all tooth geometries + BVH.

Non-bottlenecks confirmed: Treatment Setup (~1.4 s), Staging (~1.5 s) on upper real case.

---

## 6. Frontend profiling

| Probe | Result |
|---|---|
| WP-12 visibility vs rebuild (`wp12Performance.test.ts`) | filter **0.06–0.21 ms** vs mesh+BVH build **3.9–10.9 ms** (fixture-sized) |
| WP-03 mesh+BVH probe | unchanged architecture; still `three-mesh-bvh` |
| React | StageViewer orchestration only; no geometry math moved into React render |
| Memoization | Not sprayed globally; visibility uses refs + dedicated effect |

---

## 7. 3D profiling

| Topic | Finding / action |
|---|---|
| Geometry allocation | Still per-tooth `BufferGeometry` on stage/sceneGraph change |
| BVH | `prepareMeshForPicking` / `computeBoundsTree` retained |
| Arch filter / isolate / wireframe | **Incremental visibility** — no BVH rebuild |
| Target ghosts / gingiva | Built once per sceneGraph; toggled via `visible` |
| Workers stub | `geometryWorkers.ts` remains contract-only (`build_bvh` not adopted — no measured main-thread cliff justifying worker port in this WP) |
| `tooth_ref` | Preserved on `userData.toothKey` |

---

## 8. Backend profiling

| Path | Measured (upper real, WP-12 bench) |
|---|---|
| Treatment Setup | median **1.389 s** |
| Staging (3 stages) | median **1.533 s** |
| Validate in-process | **214.5 s** |
| Validate process-isolated | **105.7 s** (warm-cache follow-on; see §12) |
| Session compose (isolated+cold cache) | **104.7 s** |
| Session compose (validation cache hit) | **5.33 s** |
| `review_bundle` serialize | median **6.60 s**, **16,577,174** JSON bytes |
| Memory reopen (2× compose) | RSS delta **0.0 MB** |

---

## 9. Validation event-loop investigation

### Root cause

`TreatmentSessionStore._compose` called `GeometricValidationEngine.validate()` inside the processing `ThreadPoolExecutor` worker **in the API process**. Narrow-phase work is heavy Python/numpy. Sync FastAPI handlers (`get_processing_status`, etc.) share the process GIL → polling appeared “stuck” for ~18 minutes on dual-arch live runs even though the job was still progressing.

### Fix (semantics preserved)

- New module: `engines/validation/isolated_execution.py`
- Default: run the **same** `GeometricValidationEngine.validate` in a **spawn** `ProcessPoolExecutor` (1 worker).
- Disable with `ALIGNERSTUDIO_VALIDATION_PROCESS_ISOLATION=0`.
- Wired from `treatment_sessions._compose` via `validate_staging(...)`.
- Equivalence (upper real, 3 stages): **identical `report_id`**, status `warning`, proximity count 39, collisions 0.
- Responsiveness probe: concurrent parent thread ticks advanced during isolated validate (`responsive: true`).

### What was NOT changed

- Engine class, thresholds `(1.0, 0.001, 0.0)`, finding assembly, intra-arch pair scoping, report hashing.
- No new validation engine.
- Thread-pool `ALIGNERSTUDIO_VALIDATION_WORKERS` still defaults to 1 (prior hang evidence stands).

---

## 10. Caching strategy

| Cache | Key | Invalidation |
|---|---|---|
| Fixture reconstruction | `(artifact_root, arch, ARTIFACT_ZIP_SHA256, upload_hash\|artifact-bound)` | Explicit clear; LRU max 8; upload hash re-checked against STL checksums |
| Artifact checksum map | resolved artifact root | Cleared with fixture cache |
| Validation report | `staging_id \| engine_version \| thresholds` | Miss on new staging_id / threshold change; LRU 32 |
| Pair metrics (existing P7) | `(id(vertices_a), id(vertices_b))` within one validate | Unmoved identity reuse from staging |

**Rules:** no cross-case mutable globals returning another case’s clinical results; staging_id is content-addressed in `TreatmentStagingEngine`.

---

## 11. Memory analysis

| Observation | Evidence |
|---|---|
| Compose reopen RSS | 751.5 → 751.5 MB (**Δ 0**) after two session composes |
| Review serialize peak | tracemalloc peak_py up to ~170 MB on first serialize |
| Scene disposal | Existing BVH `disposeBoundsTree` retained; visibility path avoids churn |
| Process isolation | Validation peak alloc occurs in child process (parent peak_py lower on isolated run) |

---

## 12. Optimizations implemented

1. **Process-isolated geometric validation** — API responsiveness.
2. **Provenance-keyed validation report cache** — identical staging recomposes skip re-validate.
3. **Single-pass fixture instance reconstruction** — replaces per-instance full face scans.
4. **Fixture result + checksum caches** — warm reload ~0.0002 s.
5. **StageViewer incremental visibility** — arch/hide/isolate/wireframe without geometry rebuild.

---

## 13. Before / after benchmarks

### Fixture reconstruction (official upper)

| | BEFORE | AFTER | DELTA | METHOD |
|---|---|---|---|---|
| Warm reconstruct (audit, tracemalloc) | 11.194 s | 0.001 s (cache hit) | **~11.2 s saved** | wall + provenance cache |
| Cold wall (no tracemalloc) | (audit ~13.9 s with tracemalloc skew) | **0.835 s** | large | single-pass + OS-warm disks |
| Lower cold wall (no tracemalloc) | — | **1.680 s** | — | same |

Honest note: tracemalloc-on cold samples in the full bench (~11.8 s) inflate allocation-heavy reconstruct; wall-accurate after numbers are in `.research/tmp/wp12_performance/fixture_wall_accurate.json`.

### Geometric validation (upper, 3 stages, real teeth)

| | BEFORE | AFTER | DELTA | METHOD |
|---|---|---|---|---|
| In-process cold | 214.5 s | (engine unchanged) | — | baseline |
| Isolated follow-on | — | 105.7 s | faster follow-on; **not claimed as engine speedup** | process isolation + warm caches |
| Report equivalence | — | `report_id` match | — | identical engine |
| API thread progress during validate | blocked (WP-11) | **responsive: true** | qualitative fix | process isolation |
| Session compose w/ report cache | 104.7 s | **5.33 s** | **~99 s** | staging_id report cache |

### Frontend visibility

| | BEFORE | AFTER | DELTA | METHOD |
|---|---|---|---|---|
| Arch/wireframe toggle | full rebuild+BVH | visibility flags | rebuild avoided | StageViewer effect split |

---

## 14. External technology evaluation

| Technology | Outcome | Reason |
|---|---|---|
| `three-mesh-bvh` | **KEEP (ADOPTED)** | Already WP-03; still correct picking path |
| `trimesh` / rtree narrow-phase | **KEEP** | Clinical validation semantics |
| `manifold3d` / MeshLib | **KEEP / no new adopt** | No new boolean bottleneck justifying change |
| Celery/RQ/arq | **REJECT (this WP)** | In-process spawn pool sufficient for single-node API; external broker is WP-13 territory |
| Transferable buffers / WASM workers for review DTO | **EVALUATE later** | 16.6 MB JSON serialize is a measured cliff; not adopted without a safe DTO redesign |
| GPU validation | **REJECT** | No proven equivalence path; would risk findings drift |

---

## 15. Real-case results

- Artifact: `official_real_case_stage2_verified_v1` (28 teeth across arches; upper bench used 14).
- Upper teeth remain 14; `tooth_ref` identity unchanged; provenance `validated_real_case` / experimental labels unchanged.
- Validation status `warning`, 0 intersections, 39 proximity slots across 3 stages — isolated ≡ in-process.
- No FDI fabrication; segmentation provenance notes unchanged.
- Full dual-arch validate not re-run in this WP (`WP12_FULL_DUAL_VALIDATE=0`); WP-11 ~18 m wall-time limitation remains for dual-arch CPU cost, now **non-blocking** to unrelated API requests when isolation is on.
- No fixture substitution of clinical output.

---

## 16. Regression results

| Gate | Result |
|---|---|
| Frontend vitest | **121 passed** |
| Frontend typecheck | pass |
| Frontend lint | pass (hooks note documented; intentional sceneGraph-only deps) |
| Frontend production build | pass |
| `tests/python/test_wp12_performance.py` | **4 passed** |
| WP-01 | **11 passed** |
| WP-02…WP-10 | **115 passed** (~11.5 min) |
| P7 performance/reliability | included in earlier green run with WP-12 unit tests |

---

## 17. Remaining bottlenecks

1. Dual-arch geometric validation **wall time** still multi-minute (WP-11 ~18 m class) — isolation does not shrink CPU work.
2. `review_bundle` ~16 MB JSON — workspace transfer/serialize cost.
3. Cold process first checksum+parse still non-trivial on disk-cold machines.
4. Planning-intelligence alternatives still up to ~5× validate when expanded (kept lazy for real cases).
5. Live TIN GPU inference still environment-blocked (prior WPs).

---

## 18. Environment limitations

- No dedicated GPU for segmentation inference in this environment.
- Headless WebGL frame-rate not measured (same as WP-03).
- Full dual-arch validate opt-in only (`WP12_FULL_DUAL_VALIDATE=1`) due to multi-minute cost.
- Process pool uses `spawn` (safe with threaded API); first isolated call pays process start + pickle.

---

## 19. Targets established from measurement

| Target | Status |
|---|---|
| Responsive UI during normal interaction | Met for visibility filters (no BVH rebuild) |
| No API event-loop blocking by long validation | **Met** via process isolation (default on) |
| No unnecessary repeated geometry work | Met for unmoved staging cache + report cache + fixture cache |
| Acceptable real-case workspace load | Partially met; serialize still heavy (~6.6 s / 16 MB) |
| Stable memory on reopen | Met (Δ RSS 0 on bench reopen) |
| Interactive tooth manipulation | Unchanged WP-04 path; not regressed |
| Predictable stage switching | Visibility path predictable; stage geometry still rebuilds on `sceneGraph` change |
| Predictable validation job behavior | Isolated + cached; progress still honest (no hidden latency) |
| Export remains truthful | Not weakened; WP-10 semantics untouched |

---

## 20. Files changed

- `engines/validation/isolated_execution.py` (new)
- `engines/validation/report_cache.py` (new)
- `services/api/app/treatment_sessions.py`
- `adapters/toothinstancenet/fixture.py`
- `apps/web/src/viewer/StageViewer.tsx`
- `apps/web/src/viewer/workspace/wp12Performance.test.ts` (new)
- `scripts/wp12_performance_benchmark.py` (new)
- `tests/python/test_wp12_performance.py` (new)
- `docs/WP12_PERFORMANCE.md` (this file)
- Evidence: `.research/tmp/wp12_performance/benchmark.json`, `fixture_wall_accurate.json`, `benchmark_run.log`

---

## 21. Explicit confirmation

**WP-13 (Reliability), WP-14 (Desktop packaging), WP-15 (Final Real-Case Gate), and all later work packages were NOT started.**

WP-12 stops at performance measurement, targeted optimizations, equivalence-preserving isolation/caching, and documentation.
