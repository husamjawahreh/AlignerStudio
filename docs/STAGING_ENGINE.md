# Treatment Staging Engine

**Phase 6 status:** Implemented deterministic interpolation from a Phase 5
treatment setup proposal. No clinical movement limits, collision engine, IPR,
attachments, UI, or export are implemented.

## Pipeline

```
TreatmentPlanProposal
  → explicit StagingConfiguration
  → immutable Stage 0 from source setup
  → deterministic intermediate states
  → exact final Phase 5 target setup
  → stable stage/staging hashes
```

## Models

- `StagingConfiguration`: explicit `stage_count` and engine version. A valid
  configuration includes at least Stage 0 and a distinct final stage.
- `StageMovement`: tooth number, interpolated `ToothMovement`, and progress in
  `[0, 1]`.
- `StageToothState`: source vertices, final target vertices, current stage
  vertices, source instance ID, coordinate system, movement, provenance, and
  fixture state.
- `TreatmentStage`: stage index, stable stage ID, ordered tooth states,
  provenance, fixture state, and stage hash.
- `StagingResult`: plan ID, stable staging ID, ordered stages, assumptions,
  warnings, limitations, provenance, and fixture state.

## Deterministic Behavior

For `N` stages, stage progress is:

```text
progress = stage_index / (N - 1)
```

Stage 0 has progress `0.0` and uses the original source vertices with a zero
movement. The final stage has progress `1.0` and copies the Phase 5 target
vertices and movement exactly. Intermediate vertices and all eight movement
dimensions are linearly interpolated:

- translation X/Y/Z;
- rotation;
- tip;
- torque;
- intrusion;
- extrusion.

Tooth states are ordered by FDI tooth number. Stage hashes are SHA-256 hashes
of canonical stage content. Stage IDs and the overall staging ID are hashes of
canonical stage/configuration content and the Phase 5 plan ID. No random UUIDs,
wall-clock values, or input iteration order affect the result.

## Source/Target Immutability

The staging engine never mutates `TreatmentPlanProposal`, `TreatmentSetup`,
`TargetToothState`, or source vertex tuples. Each staged state retains:

- the original source vertices;
- the exact final target vertices;
- the current interpolated vertices;
- the original source instance ID;
- the Phase 4 coordinate system;
- the movement provenance.

This provides a future renderer with both the original case and the proposed
stage state without reconstructing either from mutable state.

## Validation Hooks

`engines/validation/hooks.py` exposes future stage-level ports for:

- per-stage movement limits;
- stage collision detection;
- contacts/proximity;
- anatomical and clinical constraints.

Phase 6 does not invoke or implement those constraints. It never silently
modifies a movement to satisfy a limit. Any future adjustment must be a new,
explicit proposal with recorded provenance and warnings.

## Missing Inputs

If the Phase 5 proposal has no setup, contains limitations, has no source or
target tooth states, or has mismatched source/target vertex counts, staging
returns an explicit limitation or raises a deterministic input error. It does
not fabricate intermediate geometry.

## Provenance

Stage provenance is inherited from the proposal and each state inherits the
Phase 5 target provenance and fixture status. Fixture-derived staging remains
fixture-labeled. No stage is marked `clinically_reviewed` by this engine.
