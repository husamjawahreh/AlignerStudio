# Automatic Treatment Setup Engine

**Phase 5 status:** Implemented deterministic treatment setup generation from
explicit objectives. Staging is not implemented.

## Pipeline

```
Identified Teeth
  → explicit TreatmentObjectives
  → explicit ToothMovements in local coordinate frames
  → immutable source scene + transformed target scene
  → basic geometry validation hooks
  → TreatmentPlanProposal
```

The planner does not infer a target from scan appearance, does not invent
objectives, and does not apply hidden movement heuristics. A caller must
provide per-tooth movement requests. Objective types currently represent:

- alignment
- spacing
- rotation correction
- arch coordination

These types classify an explicit request. They do not generate movement values
by themselves.

## Domain Models

- `TreatmentObjective`: stable ID, objective type, description, explicit
  sorted `(FDI number, ToothMovement)` requests, and assumptions.
- `ToothMovement`: local-frame translation X/Y/Z, rotation, tip, torque,
  intrusion, and extrusion. It supports deterministic addition when multiple
  objectives affect the same tooth.
- `TargetToothState`: source instance ID, immutable source vertices, separate
  transformed target vertices, coordinate system, movement, provenance, and
  fixture metadata.
- `TreatmentSetup`: source/target scene states, assumptions, warnings,
  provenance, and fixture state.
- `TreatmentPlanProposal`: deterministic plan/version IDs, objectives, setup,
  provenance, assumptions, warnings, limitations, and an explicit
  `clinical_approval=False` default.

## Geometry

Movements are expressed in the existing Phase 4 `ToothCoordinateSystem`:

- local X maps to `lateral_axis`;
- local Y maps to `anterior_axis`;
- local Z maps to `vertical_axis`;
- intrusion/extrusion are represented in the vertical local direction;
- tip, torque, and rotation apply deterministic Rodrigues rotations around
  the local frame axes.

The source `ToothInstance.mesh_vertices` are never mutated. The target setup
contains a new immutable vertex tuple for every explicitly movable identified
tooth. This is a geometric scene representation suitable for future Three.js
rendering, not a staged appliance or biomechanical claim.

## Limitations and Validation Hooks

Missing objectives, uncertain/unidentified teeth, unknown objective targets,
or missing coordinate systems return a `TreatmentPlanProposal` with explicit
`limitations` and no setup. The planner never fabricates a result.

`engines/validation/hooks.py` defines ports for:

- movement-limit validation;
- tooth-to-tooth proximity;
- collision detection;
- anatomical/clinical constraints.

Only `BasicGeometryValidator` exists in Phase 5. It checks finite, well-shaped
target vertices. No sophisticated collision, clinical, IPR, attachment, or
staging rule is implemented.

## Provenance and Plan Identity

Generated proposals use `DataProvenance.GENERATED`; fixture-derived proposals
preserve `fixture=True`. External-model or experimental upstream provenance is
not upgraded to clinical approval. Plan and version identifiers are SHA-256
hashes over canonicalized case ID, engine version, sorted objectives, target
geometry, and limitations. The hash is for deterministic identity and
reproducibility, not authorization.

## Explicit Non-Goals

- no staging or aligner timeline;
- no IPR or attachments;
- no advanced collision/proximity engine;
- no clinical thresholds or diagnostic interpretation;
- no UI or export changes;
- no external model integration.
