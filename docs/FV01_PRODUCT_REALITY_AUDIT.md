# FV-01 — Product Reality Audit + Architecture Foundation

**Work package:** FIRST VERSION FV-01  
**Authoritative roadmap:** `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md` §18 (First Version)  
**Date:** 2026-09-25  
**Scope:** Audit + architecture foundation only. **FV-02 and later packages were not started.**

## Honest success statement

FV-01 delivered a **verified architecture and product-truth foundation** on top of P0–P8 engineering.

This is **not** world-class product completion, **not** production-ready, **not** doctor-ready, and **not** a complete First Version release. It is the required foundation so later First Version packages can build a truthful dental CAD workflow without fake clinical output.

---

## 1. Product Reality Matrix

| Stage | Implementation | Real-case support | Truth state for doctor UI | Blocking? |
|---|---|---|---|---|
| REAL STL import | Exists (`cases.upload_mesh`) | Yes — files stored | Computed (file present) | No |
| Normalization | Partial (inference preprocess only) | Fixture skips re-normalize | Not Available as patient frame | Soft |
| Segmentation | Partial — backend-gated | Artifact replay works; live GPU env-dependent | Requires Review | **Yes** for live STL→instances |
| Tooth instances | Exists (14+14 on official artifact) | Yes (real mesh subsets) | Computed / Requires Review | Soft (14≠16) |
| Semantic identity | Exists (`tooth_ref`, 7-class label) | Yes | Requires Review | Soft |
| FDI identification | Partial engine; **withheld on real artifact** | No clinical FDI | **Not Available** | **Yes** for FDI workflow |
| Upper/lower assignment | Exists (upload metadata) | Yes | Computed | No |
| Orientation | Partial / engineering axes on fixture | Incomplete | Not Available / Requires Review | Soft |
| Landmarks | Partial; **None on fixture path** | No | Not Available | Soft |
| Local frames | Engineering axes for planning | Non-anatomical | Requires Review | Soft |
| Occlusion / registration | Honest stub only | Always unavailable | **Not Available** | **Yes** for bite claims |
| Treatment setup | Exists; semantic-only on real artifact | Fixture backend only (else 503) | Requires Review | **Yes** for live backends |
| Target generation | Exists (demo/heuristic objectives) | Semantic path | Requires Review | Soft |
| Staging | Exists | Yes on semantic proposal | Computed / Requires Review | Soft |
| Doctor refinement | Exists | Yes | Computed | Soft |
| Geometric validation | Exists (intra-arch) | Yes; no occlusion pairs | Computed (engineering thresholds) | Soft |
| Production / export | Engineering package | Audit reopen ≠ full restore | Requires Review / Not Available (mfg) | Soft |
| Persistence / reopen | Case JSON + session pickle | Partial | Computed | Soft |
| Gingiva | Synthetic presentation only in App path | Presentation only | Not Available (clinical gingiva) | Soft |
| Processing lifecycle | Fixed in FV-01 | Yes | Computed | Prior bugs fixed |

---

## 2. Real-case pipeline findings

**Official artifact used:** `official_real_case_stage2_verified_v1.zip` (present; SHA-256 prefix `b0f57d45e19ec1c9…`).

**Verified runtime path (fixture backend):**

```text
ZIP/DIR artifact
 → adapters/toothinstancenet/fixture.load_validated_fixture
 → 14 upper + 14 lower ToothInstance meshes (real scan subsets)
 → identity=None (no clinical FDI)
 → landmarks=None
 → engineering coordinate frames
 → semantic_only_experimental planning (when backend=toothinstancenet_fixture)
 → staging + GeometricValidationEngine (intra-arch)
 → export package with fixture/experimental provenance
```

**Critical honesty notes:**

1. Under `toothinstancenet_fixture`, uploaded case STL bytes are **not** the geometry source for segmentation — the verified artifact is. This must remain explicit; never silent substitution without doctor-visible Requires Review.
2. Manifest / artifact claims: not clinically accurate FDI; not exact 28-tooth anatomical accuracy.
3. Live ToothInstanceNet / default ONNX paths are not the working demo path without external checkpoints.
4. Plan generation returns **HTTP 503** for non-fixture backends.

---

## 3. Confirmed blockers (First Version)

1. Clinical FDI not resolved on real artifact (28 uncertain / incomplete identification).
2. Live real-STL → segmentation → plan path not production-default.
3. Occlusion/registration always unavailable.
4. Landmarks / anatomical local axes unavailable on semantic real-case path.
5. Real gingiva not in App scene graph path (synthetic presentation only).
6. Manufacturing production/export incomplete (engineering audit package only).
7. Export reopen-for-audit ≠ full editable session restore.
8. Doctor UI still not at professional CAD completeness (foundation only in FV-01).
9. Processing previously had misleading parallel-stage progress and no heartbeat/stale identity (addressed in FV-01; long-run ops still process-local ThreadPool).

---

## 4. Synthetic / fixture paths found

| Path | Silent on real upload? | Notes |
|---|---|---|
| `toothinstancenet_fixture` | **Yes relative to upload bytes** | Explicit backend env; geometry from artifact |
| `create_engineering_demo` / `engineeringFixtureBundle` | No — explicit demo | Test hook / demo |
| `syntheticGingiva.ts` | Presentation only | Documented never for clinical math |
| `PlaceholderSegmentationEngine` | Not on upload API | Invents FDI — keep off real path |
| Default ONNX without weights | Fail-closed | No silent fixture fallback |

---

## 5. UI / UX architecture findings

**Before FV-01:** Custom CAD chrome (`tokens.css`, `WorkspacePrimitives`) with partial doctor-facing softening of fixture jargon (mostly test-gated).

**FV-01 added:**

- Design System foundation: shell, top bar, panels, buttons, segmented controls, tabs, status/truth badges, property rows, numeric/slider inputs, empty/unavailable/loading/error states, confirm dialog, tooltip, tool groups, command shortcut matcher.
- Product truth vocabulary: **Verified / Computed / Requires Review / Not Available**.
- Doctor-facing copy updates: InspectionPanel no longer says “Experimental · no clinical FDI”; FixtureBadge shows Requires Review; AnalysisPanel production path avoids FIXTURE jargon.

**Not done:** Full visual redesign of every panel to ArchForm parity; orientation cube chrome; complete inspector redesign.

---

## 6. 3D architecture findings

**Existing:** Imperative Three.js `StageViewer`, selection via `toothRef`, arch toggles, labels, gizmo, camera presets, synthetic/real gingiva resolver.

**FV-01 foundation modules** (`apps/web/src/viewer/workspace/`):

- Arch layers + isolation helpers
- Semantic selection identity preservation (no FDI invention)
- Camera presets / fit-request / orientation-cube face map (architecture)
- Overlay capability registry (honest unavailable for clipping/section/measurement/validation/local frames/orientation cube)
- BVH picking via `three-mesh-bvh@0.8.3`
- Worker-safe geometry request contract (pool deferred)

**Not done:** Wire orientation cube UI, clipping tools, measurement tools, local-frame viz, BVH into StageViewer hot path, full worker pool.

---

## 7. Processing lifecycle findings

**Confirmed issues addressed:**

| Issue | Fix |
|---|---|
| Jobs lacked `input_hash`, `created_at`, `heartbeat_at`, explicit stale | Added to status payload |
| Duplicate in-flight start | Still returns same `job_id` |
| Restart orphans stay PROCESSING | Store reload → FAILED `PROCESS_RESTARTED` |
| No heartbeat stale detection | `JOB_STALE` after 120s without heartbeat (unless live executor future) |
| New job could be confused with prior mid-progress | New identity always starts `PREPARING` / 0% |
| Parallel arches reported as sequential lower-only | `SEGMENTING_BOTH` + per-arch status |
| PREPARING never completed | Now completed before validation |
| No cancel API | `POST /cases/{id}/processing/cancel` + cooperative cancel flags |
| Planning callbacks could imply READY→82% jump | New jobs never inherit progress; planning clamped to 70–87 band |

**Still process-local:** ThreadPoolExecutor in API process (no separate worker service). Offline-first preserved.

---

## 8. External technology / dependency matrix

See [`docs/FV01_DEPENDENCY_MATRIX.md`](FV01_DEPENDENCY_MATRIX.md).

---

## 9. Technologies adopted

- Existing React 18 + Vite + custom CAD tokens (extended)
- Aligner Studio Design System (`apps/web/src/design-system/`)
- Three.js (kept)
- `three-mesh-bvh@0.8.3`
- Workspace architecture modules
- Enhanced processing job lifecycle

---

## 10. Technologies rejected (and why)

- **Radix / shadcn install** — existing dense CAD chrome already stronger; patterns only
- **React Three Fiber** — no architectural value over current StageViewer owner
- **3DTeethSAM production integration** — no benchmark evidence to replace ToothInstanceNet
- **Slicer / Manifold runtime** — not required for FV-01 foundation
- **Any fabricated FDI / synthetic clinical evidence** — forbidden by FV rules

---

## 11. Files changed (primary)

### Backend
- `services/api/app/processing.py` — lifecycle rewrite
- `services/api/app/store.py` — restart recovery fields
- `services/api/app/routers/cases.py` — cancel endpoint
- `tests/python/test_fv01_processing_lifecycle.py` — new
- `tests/python/test_fv01_provenance_guards.py` — new
- `tests/python/test_processing_status_live.py` — heartbeat-aware

### Frontend
- `apps/web/src/design-system/**` — design system + truth states
- `apps/web/src/viewer/workspace/**` — 3D CAD architecture foundation
- `apps/web/src/components/FixtureBadge.tsx`
- `apps/web/src/components/InspectionPanel.tsx`
- `apps/web/src/components/AnalysisPanel.tsx`
- `apps/web/src/components/workspace/WorkspacePrimitives.tsx`
- `apps/web/src/api/client.ts`
- `apps/web/src/caseIntake.ts`
- `apps/web/src/main.tsx`
- `apps/web/src/styles/tokens.css`
- `apps/web/src/vite-env.d.ts`
- `apps/web/package.json` / lockfile — `three-mesh-bvh@0.8.3`

### Docs
- `docs/FV01_DEPENDENCY_MATRIX.md`
- `docs/FV01_PRODUCT_REALITY_AUDIT.md` (this file)

---

## 12. Tests executed and exact results

| Suite | Result |
|---|---|
| `pytest tests/python/test_fv01_processing_lifecycle.py` (+ live/P7 subset) | **19 passed** |
| `pytest tests/python/test_fv01_provenance_guards.py` | **PASS** (included in full suite) |
| `pytest tests/python` (full) | **210 passed, 2 skipped** in **177.53s** |
| `pnpm test` (apps/web) | **89 passed** (27 files) |
| `pnpm run typecheck` | **PASS** |
| `pnpm run lint` | **0 errors**, 1 pre-existing warning (`StageViewer` gizmoMode deps) |
| `pnpm run build` | **PASS** — `index.js` 779.9 kB / gzip 208.5 kB; CSS 36.3 kB |

---

## 13. Performance measurements

| Metric | Before FV-01 | After FV-01 | Notes |
|---|---|---|---|
| Frontend production JS (built) | Not re-baselined in this run | **779,939 bytes** raw / **~208.5 kB gzip** | Includes three-mesh-bvh |
| Frontend CSS | — | **36,321 bytes** | Design-system CSS added |
| Backend full pytest wall time | P8 gate ~144.6s (201 pass) | **177.53s (210 pass, 2 skip)** | Includes new FV-01 tests; environment-dependent |
| BVH picking microbench | Not previously measured | Functional enable + pick tests only | **No invented FPS/ms claims** |

No segmentation/planning runtime benchmarks were invented. Existing P8 performance benches remain opt-in (`P8_RUN_PERFORMANCE=1`).

---

## 14. Remaining First Version blockers

1. Resolve clinical tooth identity (FDI) without invention — manual correction UX + stronger identification.
2. Live segmentation path for real uploaded STLs without silent artifact substitution.
3. Occlusion/registration evidence path.
4. Anatomical landmarks + local axes on real cases.
5. Real gingiva (or honest Not Available) in the clinical workspace.
6. Treatment setup authored from real case analysis (not heuristic demo objectives).
7. Professional CAD interaction completeness (orientation cube, local-axis tools, measurements).
8. Installable desktop packaging (First Version §18.1–18.4) — **out of FV-01 scope**.
9. Clean-machine + doctor acceptance — human-required.

---

## 15. Explicitly NOT implemented in FV-01

- FV-02 or any later First Version work package
- P9 or Master Plan phase modifications
- Desktop installers (Windows/macOS/Linux packages)
- Full ArchForm-parity UI rebuild
- Orientation cube interactive chrome (architecture only)
- Clipping / section / measurement tools
- Local-axis visualization in the viewport
- Geometry worker pool implementation
- 3DTeethSAM / Slicer production integration
- ToothInstanceNet replacement
- Clinical FDI invention or occlusion fabrication
- Manufacturing aligner export
- Claims of world-class / production-ready / doctor-ready / complete

---

## Success criterion check

| Criterion | Met? |
|---|---|
| Verified architecture foundation for later FV packages | **Yes** |
| Product reality audit with evidence | **Yes** |
| No fake clinical output introduced | **Yes** |
| Explicit truth states in doctor vocabulary | **Yes (foundation)** |
| Processing lifecycle identity/stale/duplicate fixes | **Yes** |
| Prettier screenshot as success | **No — not used as criterion** |
| World-class / production-ready claim | **Not claimed** |
