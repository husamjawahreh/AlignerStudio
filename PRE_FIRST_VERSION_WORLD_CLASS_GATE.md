# PRE-FIRST-VERSION — WORLD-CLASS CLINICAL 3D GATE

## Purpose
Authoritative pre-First-Version plan for Aligner Studio. WP-14 and WP-15 remain frozen until this plan is completed and the product owner approves the result.

## Current blockers
1. Wave 1 made the REAL_CASE blocker explicit and did not execute inference. Default backend remains `onnx` with no weights. `toothinstancenet` reports `blocked_by_environment` on this host (no NVIDIA driver, torch, pointops, nvcc, or Docker). TEST_FIXTURE is still test-only. Analysis shows Blocked by environment instead of a clinical tooth count of 0. See the Wave 1 section in `docs/PRE_FIRST_VERSION_SEGMENTATION_AUDIT.md`.
2. Current segmentation presentation is not professionally acceptable as the first clinical impression.
3. Current UI is functional but not premium/world-class: duplicated Status, Data Readiness, and Processing; excessive left-panel scrolling; right-panel clipping.
4. `Analyze Case` (`POST /pipeline/{arch}`) and `Review Treatment Setup` (`POST /processing`, busy copy “Starting case analysis”) are semantically confusing.
5. Review Treatment Setup can take about 18 minutes because first-plan dual-arch geometric validation misses the report cache and runs inside session compose (“Evaluating collisions and proximity”). Setup/staging themselves are about 1–2 seconds. WP-12 isolation does not shrink that CPU time.
6. Teeth/gingiva presentation needs a major upgrade. Synthetic gingiva is already presentation-only and must stay out of clinical calculations.
7. Labels, numbering, missing/uncertain teeth and segmentation review need a professional clinical workspace. The official artifact is 7-class semantic identity, not verified FDI.

## Wave 1 — Real Segmentation Recovery
Trace the complete real path:
STL upload → bytes/hash → storage → case → job → source mesh → normalization/preprocessing → ToothInstanceNet → inference → post-processing → tooth instances → tooth_ref → arch → identity → persistence → Analysis API → 3D presentation.

Audit case id, job id, arch, input/source hashes, model/version, provenance, paths and failure state at every boundary. Find the first real divergence and fix it if the environment permits.

REAL_CASE must never silently use fixture geometry. If real inference cannot execute, report the exact runtime/environment blocker.

## Wave 2 — Segmentation Model Evaluation
Keep ToothInstanceNet as the baseline. Evaluate relevant specialized approaches such as 3DTeethSAM, DentalModelSeg and Slicer Automated Dental Tools.

Compare:
- tooth detection
- instance separation
- boundary quality
- missing teeth
- upper/lower handling
- identity/label reliability
- runtime
- memory
- GPU requirements
- reproducibility
- licensing
- integration complexity

Classify technologies as ADOPT / ADAPTER / EVALUATE / REFERENCE / REJECT. Do not replace ToothInstanceNet without measured evidence on relevant real cases.

## Wave 3 — Clinical Segmentation Review Workspace
Build a professional first clinical screen with:
- high-quality tooth meshes
- professional gingiva presentation
- upper/lower separation
- labels
- verified numbering only when genuinely supported
- tooth_ref when identity is not verified
- missing/uncertain/review states
- selected-tooth highlighting
- dental arch numbering map
- tooth-map ↔ 3D synchronization
- upper/lower filtering
- isolate/fit selected
- camera presets
- segmentation review/correction tools

Potential correction tools: refine boundary, split, merge, remove artifact, smooth boundary, correct identity, mark missing, undo/redo.

Never fabricate FDI.

## Wave 4 — Premium World-Class 3D
Make the 3D viewport the visual center.

Improve:
- tooth material response, roughness/specular behavior and depth
- gingiva transparency/translucency, depth and clean boundaries
- occlusal/frontal/lateral/orthographic cameras
- fit-to-case and fit-to-selection
- current vs target
- selected tooth
- labels
- staging
- IPR
- attachments
- collision/proximity
- validation overlays

Presentation remains separate from clinical computation. Synthetic gingiva is presentation-only unless real anatomical evidence exists.

## Wave 5 — Smart UI/UX
Do not merely polish the current layout. Rework the interaction architecture where necessary.

Principles:
- 3D viewport first
- contextual tools
- adaptive inspector
- smart widgets
- progressive disclosure
- one tool → one location
- one source of truth for status
- one source of truth for readiness
- minimal cognitive load

Remove:
- duplicated Status/Data Readiness/Processing
- repeated actions
- unnecessary badges/notifications
- long left-panel scrolling
- right-panel clipping
- technical information from primary clinical workflow

Advanced engineering details belong under Advanced Details.

## Wave 6 — Contextual Toolbar + Smart Widgets
Tools change with context.

No selection: View, Upper, Lower, Occlusion, Fit, More.
Tooth selected: Move, Rotate, Inspect, IPR, Attachment, Isolate, Measure, More.
Treatment Setup: Move, Rotate, Lock, Compare, Target, Reset.
Validation: Findings, Proximity, Collision.

Widgets should appear only when relevant: case, tooth, treatment, validation. They must not become dashboard clutter.

## Wave 7 — Workflow Simplification
Target:
CASE → ANALYSIS → TREATMENT PLAN → STAGING → REFINEMENT → VALIDATION → PRODUCTION.

`Analyze Case` means process and understand the scan.
`Treatment Plan` means create/review the actual treatment target.

`Review Treatment Setup` must not behave as a competing workflow when it represents the same planning state. If no valid plan exists: Create Treatment Plan. If one exists: Open Treatment Plan.

Preserve existing setup/version semantics.

## Wave 8 — Performance and Remaining Time
Investigate the ~17-minute Treatment Setup operation and identify exactly what consumes the time.

Use WP-12 mechanisms:
- caching
- process isolation
- incremental computation
- reusable geometry
- version-aware reuse

Use honest progress:
- `Remaining ~X min` only with a reliable estimate
- `Estimating remaining time…`
- `No reliable estimate`

Never invent ETA.

## Wave 9 — Feature Depth
Contextually expose:
- 6DOF tooth movement
- lock/exclude
- current vs target
- staging/micro-staging
- collision/proximity
- IPR
- attachments
- measurements
- tooth numbering
- missing teeth
- occlusion when real evidence exists
- validation
- production
- export

Do not create duplicate clinical engines; reuse authoritative existing systems.

## Wave 10 — Adaptive Inspector / No-Scroll
Right inspector adapts to context: case, tooth, setup or validation. No clipping, giant permanent technical panels or unnecessary scrolling. Use compact sections, responsive stacking, contextual panels and Advanced Details.

## Wave 11 — Failure Experience
Failures remain truthful but professional:
- clear human-readable problem
- actionable next step
- Retry/Review Scan when appropriate
- Advanced technical details

Never hide real failures or replace them with fixture success.

## Wave 12 — Technology Evaluation
Evaluate external technologies only where they materially improve professional quality. Use ADOPT / ADAPTER / EVALUATE / REFERENCE / REJECT. Preserve validated foundations unless evidence supports change. Do not rewrite around a popular framework without evidence.

## Acceptance Gate
The product must pass:
1. Real segmentation
2. Clinical segmentation review
3. Premium 3D
4. Professional gingiva presentation
5. Smart UI/UX
6. Clear workflow
7. Treatment-plan performance
8. Feature-depth review
9. Reliability regression
10. Full manual doctor/product-owner acceptance

Only after explicit approval:
FIRST VERSION FREEZE → WP-14 DESKTOP → WP-15 FINAL REAL-CASE GATE.

## Non-negotiable truth/safety
- Never fabricate FDI or tooth identity.
- Never fabricate segmentation.
- Never silently substitute fixture geometry.
- Never use synthetic anatomy as clinical evidence.
- GeometricValidationEngine remains authoritative.
- Validation 2.0 remains authoritative.
- WP-12 performance architecture remains authoritative.
- WP-13 reliability architecture remains authoritative.
- Preserve provenance and semantic identity.
- Do not start WP-14.
- Do not start WP-15.

## Audit findings (Command 01)

**Date:** 2026-09-26  
**Verdict:** PASS WITH BLOCKER  
**Document:** `docs/PRE_FIRST_VERSION_SEGMENTATION_AUDIT.md`

Verified, not implemented:

- Hash strings are raised only when TEST_FIXTURE binds an upload that is not byte-identical to verified `lower.stl` / `upper.stl`. Official artifact checksums match on disk. REAL_CASE does not compare uploads to that artifact and does not substitute fixture geometry.
- ToothInstanceNet checkpoint `instseg_full.ckpt` and source `424252e3d94a1565c8c2090eb5bb456b76386b93` match the contract. Inference was not run. Status: **BLOCKED BY ENVIRONMENT**.
- Segmentation Failed with 0 detected / 0 upper / 0 lower is the empty-instance result of that failed diagnostic, persisted as segmentation `failed`. WP-13 requires a new job to retry. No mid-stage resume.
- Diagnostic tests: 28 passed (fixture hash gate, artifact identity, WP-01) and 15 passed (WP-12, WP-13). Live acceptance not substituted with fixture success.
- Waves 2–12, WP-14, and WP-15 are **not** complete.

## Wave 1 result

**Date:** 2026-09-26  
**Verdict:** PASS WITH BLOCKER  
**Inference executed:** no

REAL_CASE stays on the uploaded mesh. Missing ONNX weights or a missing ToothInstanceNet GPU stack return an explicit blocker and do not load fixture geometry. Official upper/lower hashes were unchanged after the real-path run (513,417 / 171,139 and 417,249 / 139,083). Tooth counts are Not available, not a successful zero. Tests: 50 passed (Wave 1 plus WP-01, WP-12, WP-13 and related API tests); web typecheck, eslint on touched files, and production build passed. Next safe step is Wave 2 only after a CUDA/torch/pointops host exists. Do not start the UI redesign, WP-14, or WP-15.

## Implementation order
Wave 1 Real Segmentation Recovery
→ Wave 2 Segmentation Benchmark
→ Wave 3 Clinical Segmentation Workspace
→ Wave 4 Premium 3D + Gingiva
→ Wave 5 Smart UI/UX
→ Wave 6 Workflow + Treatment Plan
→ Wave 7 Performance + Remaining Time
→ Wave 8 Feature Depth + Final Polish
→ Wave 9 Manual Doctor/Product Acceptance
→ WP-14 → WP-15
