# Production UI N1 Acceptance

## Delivered

- Production workflow shell with Case, Understand, Segmentation, Plan, Review,
  Refine, Validate, and Export steps.
- Stateful workflow indicators derived from existing App state.
- Restrained production vocabulary in the visible shell.
- Engineering/demo action removed from the production DOM; fixture support is
  test-only/internal.
- Centralized production CSS tokens and dental presentation profiles.
- Premium case loading overlay and actionable empty state.
- Existing Three.js scene, DentalSceneGraph, TransformControls, and state
  ownership preserved.
- No new runtime dependencies.

## Architecture

See [PRODUCTION_UI_ARCHITECTURE.md](PRODUCTION_UI_ARCHITECTURE.md).

N1 intentionally did not add shadcn/Radix/Motion, R3F, MUI, BVH, or a second
store/viewer. No synthetic gingival envelope was added because the current
system has no gingival surface contract and presentation geometry must not be
confused with patient anatomy.

## Automated results

- Frontend tests: 19 passed.
- Backend tests: 119 passed.
- Typecheck: passed.
- Build: passed.
- Patch hygiene: passed.
- Lint: passed with one existing TransformControls hook dependency warning.

## Manual shell result

Clean page on the local Vite process at a 931x623 shared laptop viewport:

- no page-level scrolling: document height equals viewport height;
- no visible `Review mode`, `Engineering demo`, or fixture language;
- workflow labels communicate Case -> Understand -> Segmentation -> Plan ->
  Review -> Refine -> Validate -> Export;
- empty state says `Prepare a case to begin` and provides an actionable case
  setup path;
- 3D workspace remains the dominant center region.

## Remaining blockers

- A clean browser run with dense real-case segmentation still needs to complete
  through the local validated artifact to capture final 3D screenshots. Earlier
  attempts were limited by large local segmentation responses and stale Vite
  HMR sessions.
- The existing Three.js bundle warning remains at approximately 705 kB
  minified before gzip.
- The existing lint warning about the gizmo effect dependency remains.
- Real gingiva visualization awaits a genuine gingival-surface contract.
