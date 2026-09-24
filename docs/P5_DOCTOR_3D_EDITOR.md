# P5 Doctor 3D Editor

## Interaction model

The existing `StageViewer` remains the single 3D scene. Clicking a segmented
mesh selects the actual tooth object and synchronizes the right inspector.
Three.js `TransformControls` provides translate and rotate modes on that mesh.
Gizmo changes update the draft movement values; Apply is the commit boundary.

## Edit safety

Original scan buffers and source geometry remain immutable. The existing
planning/editing application rebuilds a new proposal from source geometry,
records a versioned edit, and exposes the resulting target/stage geometry.
Generated treatment is never silently overwritten.

The edit history now exposes `source: doctor` alongside the existing reason,
version, timestamp, previous movement, and new movement fields.

## Controls

The inspector provides numeric movement editing, Apply, Cancel, Reset tooth,
Lock/Unlock, Exclude/Include, Undo, and Redo. Undo/redo snapshots restore the
actual proposal bundle; API-backed sessions submit the restored movement
through the existing edit endpoint so geometry is restored rather than merely
changing displayed values.

## Recalculation

The existing Recalculate action composes the edited proposal, deterministic
staging, and geometric validation. Stage 0 remains original geometry and the
final stage reflects the applied doctor movement. No force model, FEM, or
clinical correction is performed.

## Verification

Existing doctor-editing tests verify source immutability, target geometry
changes, edit history, deterministic recalculation, and stage regeneration.
Frontend app and inspector tests remain green after the P5 controls were added.
