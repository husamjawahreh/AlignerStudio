# World-Class Foundation Implementation

## Architecture decisions

The existing application remains the single web workspace, API client, and
Three.js viewer. This command adds authoritative TypeScript contracts in
`packages/types` rather than moving the working Python/API or React modules.

- `DentalScene` describes original scans, segmented teeth, optional gingiva,
  proposed setup, current stage, overlays, provenance, and fixture state.
- `SceneLayerRegistry` is the single vocabulary for scan, arch, segmentation,
  setup, stage, validation, and measurement visibility.
- `ToothSelectionState` carries the selected instance/semantic identifier,
  optional FDI, arch, and confidence. It never invents FDI.
- `ToothMovementState` and `TreatmentStage` provide the future-facing domain
  contracts for movement and staging without implementing a planning engine.
- `PlanningEngineAdapter`, `LandmarkEngineAdapter`, and
  `GeometryEngineBoundary` keep future systems outside React and the domain.
- The current `StageViewer` remains the only viewer. It now consumes the layer
  registry for arch visibility and the app uses one selection hook.

## Files changed

- `packages/types/src/dental-scene.ts`
- `packages/types/src/index.ts`
- `apps/web/src/viewer/useToothSelection.ts`
- `apps/web/src/app/App.tsx`
- `apps/web/src/viewer/StageViewer.tsx`
- `docs/WORLD_CLASS_OPEN_SOURCE_ADOPTION_MATRIX.md`
- `docs/WORLD_CLASS_FOUNDATION_IMPLEMENTATION.md`

Existing user changes in `apps/web/src/app/App.tsx` and its tests were
preserved.

## Dependencies adopted or rejected

No dependency was added. R3F/Drei would require migrating the current viewer;
`three-mesh-bvh` is a plausible future adapter after profiling; Manifold has no
current P0 boolean workload. Full decisions are recorded in the adoption
matrix.

## Remaining P1 work

1. Add a real `DentalScene` builder that can represent raw uploaded scan
   meshes separately from segmented tooth meshes once the API exposes that
   geometry contract.
2. Add a layer panel and inspector backed by `SceneLayerRegistry`, rather than
   duplicating visibility controls in `App`.
3. Profile real-case picking and add `three-mesh-bvh` only if raycasting is a
   measured bottleneck.
4. Add the formal planning and landmark ports to the Python engine boundaries
   and connect them only through adapters.
5. Replace the explicit demo artifact configuration with a legally and
   technically verified live ToothInstanceNet-compatible model before any
   production claim.

## Known risks

- The current API returns segmented mesh geometry in diagnostic responses, so
  the viewer can show the validated real artifact, but it does not yet receive
  a separate original full-scan layer.
- `StageViewer` still rebuilds its Three.js object graph when its stage or
  visibility inputs change. It disposes resources correctly; a later P1 pass
  should profile and introduce stable geometry/material caches only if needed.
- The explicit validated artifact is experimental and must remain visibly
  labeled. It is not clinical validation and must not be silently selected for
  arbitrary uploads.