# World-Class Open-Source Adoption Matrix

Status: P0 architecture review. No external source code or model weights are
copied into AlignerStudio by this document.

| Project | Purpose | License | Exact benefit to AlignerStudio | Integration difficulty | Runtime cost | Commercial suitability | Decision | Where it belongs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| React Three Fiber | React renderer for Three.js scenes | MIT | Could make scene composition more declarative, but the current `StageViewer` already owns the single Three.js scene and works without a second renderer model | Medium to high migration cost | Low to medium | Suitable, subject to preserving notices | **REFERENCE ONLY** | `apps/web/src/viewer/` only if the existing viewer is intentionally migrated later |
| Drei | R3F helpers and controls | MIT | Useful helpers for camera controls, bounds, labels, and loaders if R3F is adopted | Medium; coupled to R3F | Low | Suitable, subject to preserving notices | **REFERENCE ONLY** | `apps/web/src/viewer/` after an R3F decision |
| three-mesh-bvh | BVH raycasting and spatial queries for Three.js meshes | MIT | Faster picking and proximity queries for large segmented meshes; concrete future fit for tooth selection | Low to medium | Small build/runtime overhead; measurable memory overhead | Suitable | **ADAPTER** | `apps/web/src/infrastructure/geometry/` or a viewer geometry adapter, after profiling current raycasting |
| Manifold / manifold-3d | Robust mesh booleans and repair operations | Apache-2.0 (library; verify exact package/version before adoption) | Reliable boolean operations for future attachments, cuts, and export repair | Medium to high | High for boolean workloads | Potentially suitable with NOTICE/license review | **REFERENCE ONLY** | `engines/geometry/` behind a geometry adapter when a concrete boolean operation is scheduled |
| Dental-CAD-Designer | Dental CAD workflow and geometry reference | License and exact upstream scope require verification | Workflow ideas for case setup, dental layers, and operator tooling | High; product architecture and licensing are not established here | Unknown | Not approved without exact license review | **REFERENCE ONLY** | Architecture documentation only |
| Slicer Automated Dental Tools / ALI-IOS | Dental segmentation, landmarks, and Slicer workflows | Exact extension/repository license must be verified per component | Potential landmark and dental-analysis adapter reference | High; Slicer runtime is not part of the web/API stack | High external runtime cost | Not approved until component licenses and data terms are verified | **ADAPTER** | `adapters/` plus a future `engines/arrangement/` port; not imported by the UI |
| OpenSourceOrtho | Clear-aligner planning architecture and safety boundaries | Apache-2.0 core, exact commit must be re-verified | Provenance, fail-closed quality gates, stage/version concepts, and export manifest patterns | Medium if independently re-implemented | Low to medium | Suitable with attribution if exact version remains compatible | **REFERENCE ONLY** | `domain/`, `engines/`, and `docs/`; never the web runtime package |
| OrthoAI v2 | Research interfaces for orthodontic AI workflows | Exact license and model/data terms are not established in this repository | Possible future planning/landmark adapter contract | High; model and data contracts are unresolved | Unknown | Not approved | **REFERENCE ONLY** | Future adapter research notes |
| TADPM | Research treatment-planning/movement approach | Exact license and checkpoint terms require verification | Candidate experimental planning engine after a stable planning port exists | High | Unknown to high | Not approved | **REFERENCE ONLY** | `adapters/` behind `PlanningEngineAdapter`, future phase only |
| STTAlign | Research aligner setup/planning approach | Exact license and checkpoint terms require verification | Candidate experimental setup engine for benchmark comparison | High | Unknown to high | Not approved | **REFERENCE ONLY** | `adapters/` behind `PlanningEngineAdapter`, future phase only |
| 3DTeethSAM | Research tooth instance segmentation | Exact repository, SAM2, checkpoint, and dataset terms require verification | Alternative segmentation benchmark if ToothInstanceNet cannot be used | High; GPU/model/data stack differs from current pipeline | High | Not approved | **REJECT for P0** | Research benchmark area only; never a silent production fallback |
| ToothInstanceNet / 3dteethland | Tooth-instance segmentation and semantic labels | MIT source; checkpoint/data terms remain separate and unresolved | Existing validated artifact provides real mesh instances for the current demo workflow | High runtime requirements; adapter already exists | High GPU cost for live inference | Artifact is not approved as a commercial model | **ADAPTER** | Existing `adapters/toothinstancenet/` and `engines/segmentation/`; no replacement |

## P0 Decisions

- No new npm dependency is adopted in this command. Three.js already supplies
  the current renderer and raycaster, and there is no measured bottleneck that
  justifies BVH yet.
- No Manifold dependency is adopted because no current P0 operation requires a
  boolean or mesh repair kernel.
- ToothInstanceNet and its validated real artifact remain the segmentation
  path. The fixture backend is explicit, matching-artifact-only, and remains
  experimental in the UI/API.
- OpenSourceOrtho informs architecture decisions but is not imported as a
  runtime application or planning engine.