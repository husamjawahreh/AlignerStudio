# AlignerStudio Treatment Plan Pipeline

This document describes the intended end-to-end orthodontic treatment
planning pipeline, and precisely which parts are implemented through Phase 13
versus planned for later phases.

## Full Target Pipeline

```
STL case
  → dental mesh validation
  → automatic tooth segmentation
  → tooth identification
  → tooth coordinate systems
  → initial arch analysis
  → automatic setup generation
  → staged tooth movement
  → collision/validation checks
  → 3D treatment-plan review
  → doctor adjustments
  → restaging
  → export
```

Target end-user UX:

```
Upload Case → Analyze Case → Generate Treatment Plan → Review Stages
  → Modify → Recalculate → Export
```

## Phase Status

| Pipeline Step                | Phase 13 Status                               | Notes                                                                                                                                                                                                                                                                                          |
| ---------------------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| STL upload                   | **Implemented**                               | `POST /cases/{id}/uploads`, stored on disk, metadata recorded on `Case`.                                                                                                                                                                                                                       |
| Mesh validation              | **Implemented (basic)**                       | `engines/geometry` checks file readability, triangle count, watertightness, degenerate faces using `trimesh`. Thresholds documented in [CLINICAL_BOUNDARIES.md](CLINICAL_BOUNDARIES.md).                                                                                                       |
| Automatic tooth segmentation | **Configuration gate implemented**            | Uploaded cases require an external ONNX artifact plus verified contract sidecar/hash/license metadata. The API returns explicit model/segmentation diagnostic states and never substitutes fixtures. No legally cleared artifact is configured in this workspace.                              |
| Tooth identification         | **Implemented (deterministic geometry)**      | `engines/arrangement.ToothIdentificationEngine` requires caller-supplied upper/lower context, validates complete geometric slots, assigns FDI only when rules pass, and distinguishes identified/uncertain/unidentified. No arbitrary instance-order labels.                                   |
| Tooth coordinate systems     | **Implemented (descriptive frame)**           | Every identified tooth receives a stable orthonormal lateral/anterior/vertical frame and descriptive surface landmarks. No movement is applied.                                                                                                                                                |
| Initial arch analysis        | **Implemented (descriptive geometry)**        | `engines/arrangement.ArchAnalysisEngine` provides centerline points, lateral ordering, width spans, anterior/posterior relationships, and consecutive tooth distances. No diagnostic thresholds.                                                                                               |
| Automatic setup generation   | **Implemented (deterministic proposal)**      | `engines/planning.TreatmentPlanningEngine` consumes explicit objectives and identified teeth, transforms immutable source geometry into separate target states, and emits stable plan/version hashes with assumptions, warnings, limitations, and provenance.                                  |
| Staged tooth movement        | **Implemented (deterministic interpolation)** | `engines/planning.TreatmentStagingEngine` creates immutable Stage 0, explicit intermediate stages, and an exact final Phase 5 target stage. All existing movement dimensions are interpolated; no clinical limits or automatic corrections are applied.                                        |
| Collision/validation checks  | **Implemented (geometric only)**              | `engines/validation.GeometricValidationEngine` performs configured mesh proximity, contact, and triangle-level intersection checks across stages, with deterministic per-tooth/stage/report results. It does not apply clinical limits or modify plans.                                        |
| 3D treatment-plan review     | **Implemented (read-only review workspace)**  | React/Three.js workspace provides stage slider/playback, previous/next navigation, tooth selection, original/reference toggle, arch visibility, wireframe mode, inspection panel, validation summary, and explicit real-data unavailable state. Local preview data is visibly fixture-labeled. |
| Doctor adjustments           | **Implemented (explicit application layer)**  | `TreatmentEditingApplication` records movement changes, preserves immutable source geometry and history, supports apply/cancel/reset, and distinguishes original/doctor-edited/recalculated proposals.                                                                                         |
| Restaging                    | **Implemented (deterministic composition)**   | Recalculation composes edited proposal → `TreatmentStagingEngine` → `GeometricValidationEngine`; no automatic movement correction is applied.                                                                                                                                                  |
| IPR proposals                | **Implemented (review-only geometry)**        | `TreatmentProposalEngine` reports adjacent-tooth geometric deltas, measurements, confidence, warnings, and `needs_review`/`unable_to_determine` states. No clinical maximum is invented.                                                                                                       |
| Attachment proposals         | **Implemented (review-only metadata)**        | Objective/angular-movement candidates include tooth, reference frame, orientation, reason, confidence, warnings, and undetermined dimensions. No validated attachment geometry is generated.                                                                                                   |
| Export                       | **Implemented (engineering package)**         | `TreatmentExportEngine` validates immutable plan/staging/validation/proposal relationships, writes ordered stage STL files, structured reports, SHA-256 manifest, and deterministic ZIP package. Fixture/generated data is visibly labeled; no clinical or manufacturing export claim is made. |

## Explicit Non-Goals for Phase 11

- No external model weights are bundled and no ToothGroupNetwork integration
  is permitted. MeshSegNet is only an adapter target pending legal and
  technical verification; see [REUSE_MATRIX.md](REUSE_MATRIX.md).
- No tooth identification or FDI assignment occurs during segmentation.
- No clinical movement limits, IPR, attachments, or clinical validation rules
  are implemented.
- No automatic restaging or movement correction is performed after findings.
- No clinical correction based on rules is implemented.
- No final clinical approval, automatic clinical decision, advanced attachment
  shape generation, or manufacturing/export is implemented.
- No hidden objective heuristics are applied; all movement requests must be
  explicit in `TreatmentObjective` values.
- No automatic plan modification is performed to satisfy future constraints.
- No clinical diagnostic interpretation is applied to arch measurements.
- No real setup/staging algorithm — the "plan" is a single fixture stage
  equal to the validated input mesh, never claimed as clinically valid.
- No cloud storage, patient sharing, DICOM, manufacturing-specific aligner
  files, external ML integration, or clinical approval workflow.

## Fixture Labeling Contract

Any object produced by a placeholder engine must set:

- `provenance: "fixture"`
- `fixture: true`
- `notes` explaining what is missing (e.g. `"Segmentation not yet
implemented; returns static FDI fixture."`)

The production segmentation engine has a different contract: model output is
tagged `experimental` by default, and missing model/runtime errors are
surfaced. It never silently invokes the fixture engine.

The frontend must visually flag `fixture: true` data (e.g. a banner/badge)
so it is never confused with real clinical output.
