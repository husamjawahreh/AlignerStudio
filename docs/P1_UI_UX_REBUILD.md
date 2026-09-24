# P1 UI/UX Rebuild

## Workspace architecture

The former single review page is now a fixed-height desktop CAD shell with
application-level workspace navigation:

1. Case
2. Analysis
3. Segmentation
4. Treatment Plan
5. Stage Review
6. Tooth Editor
7. Validation
8. Export

The shell has one header/navigation region, one left tool panel, one dominant
center viewport, one right inspector, an optional bottom stage timeline, and a
compact status bar. Panels own their scrolling. The browser frame does not
scroll during the normal desktop workflow.

## State architecture

No second case store or scene store was introduced. `App` remains the
authoritative state owner and continues to use the existing API client,
`ReviewBundle`, pipeline diagnostics, treatment editing, and ToothInstanceNet
geometry. `workspace` is a small view-selection state only. Existing tooth
selection, stage, movement, upload, and provenance state survives navigation.

The reusable shell primitives live in
`apps/web/src/components/workspace/WorkspacePrimitives.tsx`:

- `AppShell`
- `WorkflowHeader`
- `LeftToolPanel`
- `RightInspector`
- `BottomTimeline`
- `WorkspaceContainer`
- `ViewerOverlay`
- `StatusBar`

## Viewer behavior

The existing `StageViewer` remains the single Three.js renderer. Switching
workspaces changes the surrounding inspector and tools without replacing the
scene contract or changing the API/data loading path. Real ToothInstanceNet
geometry remains the source for real-case segmentation review; fixture and
experimental provenance remain visible.

## Scroll behavior

`html`, `body`, and `#root` are fixed to the viewport for desktop use. The CAD
shell uses `minmax(0, 1fr)` tracks and `overflow: auto` only on the left and
right panels. The center viewport and stage timeline stay inside the available
height. A responsive fallback permits document scrolling below the desktop
clinical-workstation breakpoint.

## Files changed

- `apps/web/src/app/App.tsx`
- `apps/web/src/components/workspace/WorkspacePrimitives.tsx`
- `apps/web/src/styles/global.css`
- `docs/P1_UI_UX_REBUILD.md`

## Validation

- Frontend typecheck passed.
- Focused app tests passed: 6/6.
- Full frontend tests passed before P1 and must be rerun after this final UI
  slice.
- Root lint/typecheck are available through `pnpm lint` and `pnpm typecheck`.
- Backend tests remain independent and preserve the real-artifact pipeline.

## Remaining issues

- A future pass should add a true scene/layer panel component backed by the
  existing `SceneLayerRegistry` rather than keeping a compact set of layer
  toggles in `App`.
- The API still returns segmented geometry through diagnostics rather than a
  dedicated original-scan scene payload.
- The desktop UI is the primary target. Mobile uses a stacked fallback rather
  than a full clinical workstation interaction model.
- The current fixture artifact remains experimental and is not a clinical
  model or approval workflow.
