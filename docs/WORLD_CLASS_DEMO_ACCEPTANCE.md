# World-Class Demo Acceptance

## Scope

P7 hardening audit for the P0-P6 AlignerStudio foundation. No new
experimental feature was added in this pass.

## End-to-end flow

The application has one coherent shell and one authoritative `App` state owner:

`Create Case -> Import -> Analysis -> Segmentation -> Review -> Generate Target Setup -> Review Target -> Stage -> Doctor Edit -> Recalculate -> Validate -> Export`

Existing API-backed paths cover case creation, STL upload/validation,
ToothInstanceNet artifact review, deterministic target setup, stage generation,
doctor edits, recalculation, geometric validation, and auditable export.

## Acceptance results

- P0-P6 automated suites remain green.
- Frontend tests: 19 passed.
- Backend tests: 119 passed.
- TypeScript typecheck: passed.
- Lint: passed with one existing React hook dependency warning in
  `StageViewer`.
- Production build: passed.
- Patch hygiene: passed.
- API health: `200 OK`.
- Main desktop shell has fixed browser height; panels own overflow.
- Existing workspace browser checks previously measured equal document and
  viewport heights at the tested desktop viewport.
- No new package dependency was introduced.
- No second viewer, global store, or model path was introduced.

## Provenance

The real-case demonstration uses the validated ToothInstanceNet artifact:

- repository: `nnistelrooij/3dteethland`;
- artifact: `official_real_case_stage2_verified_v1.zip`;
- source contract: ToothInstanceNet/3dteethland instances stage;
- status: experimental and fixture-labeled;
- clinical accuracy claim: false;
- exact FDI clinical validity: not claimed.

The artifact remains behind the existing explicit fixture backend and is never
a silent fallback for arbitrary uploads.

## Performance observations

- Frontend production build completes successfully.
- Three.js bundle remains the measured build warning: approximately 704 kB
  minified before gzip. No code-splitting change was introduced because P7
  does not add unmeasured optimization.
- STL parsing occurs outside the render loop when the scene graph changes.
- Viewer cleanup disposes geometries/materials and TransformControls.
- Selection updates material/label/gizmo state through refs without rebuilding
  the scene.
- Stage playback uses a bounded timer and cleans it up on unmount.
- Backend full test suite completes in approximately 145 seconds on this
  workstation; the heaviest work is geometric validation/export fixture data.

## Known limitations

- A clean browser-driven real-case run could upload and validate both STL
  files through the existing local API, but the shared browser harness did not
  complete the long segmentation request reliably. This prevents claiming
  full visual manual acceptance for the dense real-case canvas in this session.
- The current validator reports computed geometric counts/findings but does
  not provide screen-space marker coordinates for individual contacts or
  collisions.
- Clinical movement constraints are explicitly unavailable; no clinical
  threshold is invented.
- Attachment records remain proposals with `generated: false` when geometry
  and dimensions are unavailable.
- Export is an auditable engineering/review artifact and never indicates
  clinical approval.
- The existing Three.js lint warning about a hook dependency remains.

## Unresolved blockers

1. Complete a clean workstation browser run with the API configured for the
   validated artifact and capture canvas, tooth-selection, stage playback,
   doctor-edit, recalculation, validation, and export screenshots.
2. Profile the dense real-case segmentation response and consider a streamed
   scene endpoint if payload size becomes a measured bottleneck.
3. Add screen-space finding marker coordinates only when the validation engine
   supplies them from actual geometry.

P7 stops here. No further experimental features were added.
