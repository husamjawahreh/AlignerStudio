# Production UI Architecture

## Current stack

- React 18 + TypeScript + Vite.
- Three.js imperative renderer with OrbitControls and TransformControls.
- CSS token system in `apps/web/src/styles/global.css`.
- Vitest, Testing Library, ESLint, and strict TypeScript.
- No shadcn/ui, Radix, Motion, MUI, R3F, or animation framework is installed.

No dependency was added in N1. Existing primitives are sufficient for the
production shell and adding a UI framework would create a second visual system.

## Ownership

- `App.tsx` owns the existing case, pipeline, review, treatment, selection, and
  edit state. N1 does not create a store or duplicate state.
- `StageViewer.tsx` owns the single Three.js renderer and scene lifecycle.
- `sceneGraph.ts` owns the viewer input contract.
- Python domain/engines own planning, staging, validation, and export.
- API client owns HTTP translation only.

## Reusable UI primitives

- Existing shell primitives in `components/workspace/WorkspacePrimitives.tsx`.
- N1 production primitives in `components/production/ProductionPrimitives.tsx`:
  `CaseLoadingOverlay`, `ProductionEmptyState`, `StatusPill`,
  `SuggestionCard`, and `InspectorSection`.
- Workflow state helpers in `apps/web/src/workflow.ts`.

## Reusable 3D primitives

- Existing `DentalSceneGraph` and `StageViewer` remain authoritative.
- Existing OrbitControls, TransformControls, STLLoader, and disposal lifecycle
  remain in place.
- `viewer/materialProfiles.ts` centralizes enamel, gingiva, analytical
  highlight, and movement-vector presentation parameters.
- Analytical geometry remains separate from presentation materials.

## Design tokens

The centralized CSS token layer now includes app/workspace surfaces, elevated
panels, borders, typography, restrained gold accent, enamel current/selected/
target colors, arch colors, gingiva, collision, and contact colors. Raw scan
and treatment geometry are not recolored in domain or API code.

## Workflow model

`workflow.ts` defines `WorkflowStep`, `WorkflowStepStatus`, `WorkflowAction`,
and `WorkflowSuggestion`. `buildWorkflowSteps` derives current, complete,
ready, and blocked states from existing App state. Navigation remains a view
selection, not a second workflow store.

## Intentionally not changed

- ToothInstanceNet adapter or real artifact pipeline.
- Planning/staging/validation/export algorithms.
- Three.js renderer architecture.
- API/domain provenance model.
- Existing engineering fixture support in tests and internal data.
- No synthetic gingival envelope was added: the current API has no gingival
  surface contract, and inventing one in N1 would risk confusing presentation
  geometry with patient anatomy.

## Remaining production boundary

The doctor-facing shell now uses production vocabulary and hides the engineering
/demo action. Fixture metadata remains available to tests and internal export
provenance, but a clean real-case validation run is still required before any
production clinical claim.
