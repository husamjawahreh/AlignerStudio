# WP-03 — World-Class 3D Workspace

**Work package:** FIRST VERSION WP-03  
**Date:** 2026-09-25  
**Authoritative roadmap:** `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md`  
**Active First Version plan:** `Aligner_Studio_First_Version_World_Class_Plan.md`  
**Baselines:** `docs/FV01_PRODUCT_REALITY_AUDIT.md`, `docs/WP01_REAL_CLINICAL_DATA_PIPELINE.md`, `docs/WP02_DENTAL_INTELLIGENCE_2.md`  
**Scope:** Professional orthodontic CAD 3D workspace foundation (architecture + interaction).  
**Explicit stop:** **WP-04 and all later work packages were NOT started.**

---

## 1. Verdict

**PASS WITH BLOCKER** (same GPU/runtime blocker as WP-01/WP-02 for live TIN inference; headless WebGL frame-rate not measured).

- The central viewport (`StageViewer`) is the sole live Three.js clinical CAD workspace.
- FV-01 workspace foundations are **wired** into the hot path (BVH picking, fit targets, hierarchy, overlays, selection identity).
- Real-case tooth instances (official artifact) render via the existing WP-01 → review mesh path with stable `tooth_ref` selection.
- Upper/lower isolation is semantic (arch identity), with optional isolate-selected-tooth.
- Camera presets + fit case / fit tooth / fit arch are deterministic.
- Inspection exposes WP-02 truth states honestly (no fabricated FDI/axes).
- Overlay registry is extensible; unavailable overlays stay unavailable.
- Synthetic gingiva remains presentation-only (`clinicalGeometry=false`).
- Resource disposal includes BVH trees.
- WP-01 / WP-02 / P8 regressions remain green.

This is **not** doctor-ready, production-ready, or world-class completion.

---

## 2. Architecture

```
DOMAIN / CLINICAL STATE (case, segmentation, WP-02 intelligence, validation)
        ↓
VIEW MODEL (ReviewToothMesh, DentalSceneGraph, selection keys, layer controls)
        ↓
3D SCENE (CaseRoot hierarchy — presentation objects stamped with toothKey)
        ↓
RENDERING / GPU (Three.js WebGLRenderer + three-mesh-bvh picking)
```

React orchestrates UI/application state. Geometry computation stays out of React components. Selection source of truth is semantic `tooth_ref` / `reviewToothKey`, not mesh array index.

---

## 3. Existing viewer audit

| Finding | Detail |
|---|---|
| Sole live viewer | `apps/web/src/viewer/StageViewer.tsx` |
| Dead duplicate | `ViewerShell.tsx` — deprecated; not mounted |
| FV-01 foundations unwired | `viewer/workspace/*` existed (picking, camera, overlays, arch filters) but StageViewer used inline raycast |
| Selection | Already preferred `toothRef` via `reviewToothKey`; not stamped as `userData.toothKey` |
| Fit | Case-only; no fit-selected / fit-arch |
| BVH | Package present; not in StageViewer hot path |
| Overlays | Ghost/vectors/gingiva/scan only; no registry lifecycle |
| Inspection | 2D panel without WP-02 truth states |
| Validation | Panel-only; no dishonest 3D clinical overlays |

**Decision:** Extend and wire — do not rewrite StageViewer onto R3F; do not create a second renderer.

---

## 4. Scene architecture

Named hierarchy from `createCaseSceneHierarchy()`:

```
AllContent
└── CaseRoot
    ├── UpperArch { UpperTeeth, UpperGingiva, UpperOverlays }
    ├── LowerArch { LowerTeeth, LowerGingiva, LowerOverlays }
    ├── OcclusionLayer (hidden; truthState=not_available)
    ├── TreatmentLayer (ghost + movement vectors)
    ├── ValidationLayer / MeasurementLayer (reserved)
    ├── ReferenceLayer (original scans)
    ├── InteractionLayer / AnnotationLayer
```

---

## 5. Domain / view separation

| Layer | Owner |
|---|---|
| Clinical intelligence | WP-02 `CaseDentalIntelligence` (API) |
| Review meshes | `ReviewToothMesh` / `DentalSceneGraph` |
| Selection state | `useToothSelection` → `selectedToothRef` + multi-select foundation |
| Scene objects | Presentation only; `userData.toothKey` / `toothRef` mirrors domain keys |

Heavy geometry is not stored in React state beyond the existing review mesh contracts.

---

## 6. Selection architecture

- Click → BVH-accelerated `pickToothFromPointer` → semantic `toothKey`
- Hover feedback (visual role `hovered`) without claiming clinical status
- Selected / multi-selected foundation
- Empty-canvas click clears selection
- Selection persists across stage remounts via `preserveSelectionAcrossTeeth`
- Mesh stamp: `userData.toothKey` + `userData.toothRef` + `arch` + `instanceId`
- **Never** uses array index / React key / screen position as identity

Visual roles (`selectionVisuals.ts`): normal, hovered, selected, multi_selected, validation_warning/error, requires_review, unavailable, treatment_target, hidden — mapped without inventing clinical verification.

---

## 7. Arch isolation

- Modes: Both / Upper / Lower (`WorkspaceViewportChrome`)
- Driven by semantic `tooth.arch`, not mesh ordering
- Optional **Isolate tooth** by `tooth_ref` / `reviewToothKey`
- Helpers: `filterTeethByArchVisibility`, `setArchGroupVisibility`

---

## 8. Camera / navigation

- Orbit / pan / zoom (`OrbitControls` + damping)
- Presets from `CAMERA_PRESETS`: Occlusal, Front, Back, Left, Right, Upper, Lower
- Fit case / Fit tooth / Fit arch (`resolveFitBounds` + smooth tween)
- Dental-scale near/far from bounding sphere
- `ResizeObserver` + window resize for panel layout changes
- No decorative camera animation beyond deterministic framing transitions

---

## 9. Rendering / material system

- Existing `dentalMaterialProfiles` retained (presentation-only)
- Arch-tinted enamel, selection, ghost, gingiva real vs visualization
- ACES tonemap, soft shadows, RoomEnvironment PMREM
- Anti-aliasing with capped pixel ratio

---

## 10. Gingiva handling

- `resolveGingivaPresentation` unchanged: real when usable, else synthetic envelope
- Synthetic meshes stamped `presentationOnly` + `clinicalGeometry=false`
- Overlay registry marks gingiva provenance `presentation_only`
- `isClinicalGeometryOverlay(gingiva) === false`

---

## 11. Overlay architecture

Runtime `createOverlayRegistry()` with enable/visible/truthState/source/lifecycle:

| Overlay | Default | Truth |
|---|---|---|
| original_scan | off | computed (when scans exist) |
| gingiva | on | not_available (synthetic) / presentation |
| target_ghost | on | requires_review |
| movement_vectors | on | computed |
| tooth_labels | on | computed |
| gizmo | on | requires_review |
| validation / measurement / local_frames / occlusion | disabled | not_available |

No fabricated clinical overlays. Mesh PCA is **not** shown as clinical axes.

---

## 12. Truth-state presentation

- Viewport chrome shows identity / geometry / occlusion / treatment-setup readiness from WP-02
- Inspection panel shows FDI / geometry / landmarks / clinical axes / roots with explicit truth labels
- `requires_review` visual role is distinct from selected/verified warmth
- Unavailable fields say Not Available — not a disabled fake value

---

## 13. Inspection panel

When a tooth is selected:

- Stable tooth ref
- FDI only if present (+ truth state)
- Arch, confidence (or Not Available when 0/null)
- WP-02 intelligence block when document present
- Validation status/message from actual tooth findings
- Movement fields only when treatment data exists

---

## 14. Performance architecture

- BVH picking enabled once per scene mount
- BVH trees disposed on case teardown (`disposeObjectTree`)
- Selection/hover visuals update without full scene rebuild
- Scene rebuild still occurs on geometry/layer dependency changes (existing model)
- `ViewerShell` not mounted (avoids dual GPU contexts)

---

## 15. Real-case evidence

Official artifact `official_real_case_stage2_verified_v1`:

| Metric | Value |
|---|---|
| Tooth instances | 28 (14 upper + 14 lower) |
| Unique `tooth_ref` | 28 |
| FDI present | 0 (not fabricated) |
| Total vertices / faces | 97,649 / 188,974 |
| Load+serialize (non-GPU) | **3407.7 ms** |
| Live WebGL FPS | **Not measured** (headless) |
| Live TIN inference | **Blocked** (no torch/CUDA) |

Presentation path consumes the same serialized tooth instances as WP-01 persistence (test loader for evidence only; REAL_CASE production path unchanged).

---

## 16. Tests

| Suite | Result |
|---|---|
| `wp03Workspace.test.ts` | Scene hierarchy, visuals, isolation, fit, overlays, picking, disposal |
| `wp03InspectionChrome.test.tsx` | Inspection truth states + arch chrome |
| `wp03Performance.test.ts` | Local presentation timing probe |
| `workspaceFoundation.test.ts` | Updated orientation-cube availability |
| WP-01 + WP-02 Python | **23 passed** |
| P8 workflow + WP-02 FE | **passed** |

---

## 17. Measurements

**Engineering fixture presentation probe (vitest):**

| Metric | Observed |
|---|---|
| Tooth count | 8 |
| Hierarchy create | 0.73 ms |
| Mesh build + BVH | 3.92 ms |
| Bounds | 0.98 ms |
| Total | 5.64 ms |

**Official real-case (Python serialize evidence):** see §15.

**Not measured:** interactive selection latency in browser, sustained FPS, GPU memory after case replacement (no reliable headless WebGL).

---

## 18. Limitations

- No tooth manipulation / Treatment Setup / Staging / IPR / Attachments / Occlusion CAD features
- 3D validation overlays not spatially bound (findings remain in panels)
- Measurement overlays reserved
- Orientation-cube chrome uses toolbar presets (not a literal cube widget)
- Geometry workers remain a contract stub
- Full scene rebuild still occurs for major layer/geometry prop changes
- Live GPU TIN inference blocked in this environment

---

## 19. Environment blockers

- No `torch` / CUDA for live ToothInstanceNet (same as WP-01/WP-02)
- Headless CI lacks WebGL for renderer memory/FPS measurement
- Non-GPU intelligence + presentation evidence use genuine official artifact geometry

---

## 20. Explicit confirmation — WP-04 was NOT started

- No tooth manipulation CAD tools beyond existing refinement gizmo wiring
- No Treatment Setup productization
- No Staging workflow redesign
- No IPR / Attachments / Occlusion implementation
- No Production CAD
- No new research-model integration
- ToothInstanceNet not replaced
- GeometricValidationEngine not weakened

**STOP after WP-03.**
