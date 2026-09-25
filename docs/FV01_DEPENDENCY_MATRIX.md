# FV-01 Dependency / Technology Matrix

**Work package:** FIRST VERSION FV-01 — Product Reality Audit + Architecture Foundation  
**Date:** 2026-09-25  
**Rule:** Do not install blindly. Decision = professional quality + speed + performance + maintainability + license + replaceability.

| Technology | Purpose | License | Project compatibility | Performance impact | Replacement strategy | Adoption decision | Reason |
|---|---|---|---|---|---|---|---|
| **Existing React 18 + Vite + custom CSS tokens** | App shell, dense CAD chrome | MIT (React/Vite) | Already shipped through P0–P8 | Low | Keep; design-system layers on top | **ADOPT (keep)** | Stronger for dense clinical-CAD look than a generic component kit rewrite |
| **Radix Primitives** | Accessible dialogs/menus/tooltips | MIT | Compatible, but would parallel existing CSS | Low runtime | Replace with design-system ConfirmDialog/Tooltip | **REJECT (now)** | Existing design tokens + new FV-01 primitives cover needed surfaces without second styling system |
| **shadcn/ui** | Copy-paste UI patterns | MIT (patterns) | Tailwind-centric; project is custom CSS | Medium migration | Pattern reference only | **REJECT (install)** / **ADOPT (patterns)** | Use interaction patterns (segmented controls, property rows); do not import Tailwind/shadcn stack |
| **Three.js r166** | 3D workspace renderer | MIT | Already in `apps/web` | Baseline | Keep | **ADOPT (keep)** | Production viewer already imperative Three.js |
| **React Three Fiber** | Declarative Three.js in React | MIT | Conflicts with mature `StageViewer` ownership | Medium migration risk | Keep imperative viewer; revisit only if StageViewer is rewritten | **REJECT (now)** | No architectural value over current single-scene owner; P0 matrix already REFERENCE ONLY |
| **three-mesh-bvh 0.8.3** | Accelerated raycasting / spatial queries | MIT | Compatible with Three 0.166 | Small memory; faster picks on dense meshes | Disable via `enableBvhAcceleration` boundary; fall back to stock Raycaster | **ADOPT** | FV-01 picking foundation; optional acceleration behind `viewer/workspace/picking.ts` |
| **Web Workers / transferable buffers** | Heavy geometry off main thread | N/A (platform) | Compatible | High UI responsiveness gain when used | Worker pool can be swapped | **ADOPT (architecture)** | Contract in `geometryWorkers.ts`; full pool deferred — not silently doing clinical work |
| **Dental-CAD-Designer** | CAD architecture reference | Unverified | Reference only | N/A | N/A | **REFERENCE ONLY** | Layer separation ideas only — not copied |
| **OpenSourceOrtho** | Clear-aligner planning/review reference | Apache-2.0 (re-verify) | Reference only | N/A | N/A | **REFERENCE ONLY** | Workflow / provenance patterns — not imported |
| **ToothInstanceNet** | Tooth instance segmentation baseline | MIT source; checkpoint terms separate | Already adapted | High for live GPU | Adapter-swappable after benchmark | **KEEP BASELINE** | Do not replace without measured evidence |
| **3DTeethSAM** | Segmentation benchmark candidate | Unverified | Research only | High | Benchmark adapter only | **REJECT (production)** | Benchmark candidate only; no production treatment integration |
| **Slicer Automated Dental Tools** | Landmarks / orientation concepts | Per-component | Not in web/API stack | High external | Future adapter | **REFERENCE / FUTURE ADAPTER** | Concepts only in FV-01 |
| **Manifold / manifold-3d** | Mesh booleans | Apache-2.0 | Not needed yet | High when used | Geometry adapter | **REJECT (now)** | No FV-01 boolean requirement |

## Technologies adopted in FV-01

1. Existing React + Vite + custom design tokens (extended)
2. Aligner Studio Design System foundation (`apps/web/src/design-system/`)
3. Three.js (kept)
4. `three-mesh-bvh@0.8.3` for picking acceleration foundation
5. Workspace architecture modules (`apps/web/src/viewer/workspace/`)
6. Processing job lifecycle fields + stale/cancel semantics (API)

## Technologies rejected in FV-01

1. Radix / shadcn full install — existing CAD chrome is stronger for this product
2. React Three Fiber / Drei — would rewrite a working viewer without clear gain
3. 3DTeethSAM / Slicer / Manifold production integration — no benchmark/evidence or need yet
4. Blind replacement of ToothInstanceNet — forbidden without measured evidence
