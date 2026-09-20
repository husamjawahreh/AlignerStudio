# Doctor Treatment Editing and Restaging

**Phase 9 status:** Implemented as an immutable application layer plus a
read-only/editable review workflow for the current engineering fixture. No
clinical movement limits, automatic correction, IPR, attachments, export, or
external ML integration is included.

## Lifecycle

```
Original generated proposal
  → explicit doctor edit draft
  → Apply / Cancel / Reset
  → doctor-edited proposal + edit history
  → Recalculate
  → TreatmentStagingEngine
  → GeometricValidationEngine
  → recalculated proposal + updated stages + validation report
```

## Application Layer

`engines/planning/editing.py::TreatmentEditingApplication` owns treatment
editing behavior. React components do not calculate treatment geometry or
rewrite proposals.

The application layer provides:

- `apply_edit`: validates finite movement values, creates an explicit
  `DoctorMovementEdit`, and rebuilds a proposal copy from immutable source
  geometry;
- `cancel`: discards an uncommitted draft by retaining the current immutable
  proposal;
- `reset_tooth`: restores the first recorded movement for one tooth and adds a
  `doctor_reset` history record;
- `reset_all`: restores all edited teeth through explicit reset records;
- `recalculate`: rebuilds the recalculated proposal, runs
  `TreatmentStagingEngine`, then runs `GeometricValidationEngine`.

## Edit Record

Each edit records:

- tooth number;
- previous movement;
- new movement;
- timestamp supplied by the caller;
- deterministic edit/version identifier;
- provenance;
- reason (`doctor_edit` or `doctor_reset`).

The original proposal remains unchanged. Source scan vertices and faces are
copied by immutable dataclass value and are never transformed in place.

## Proposal Lifecycle

`ProposalKind` distinguishes:

- `original_generated` — Phase 5 generated proposal;
- `doctor_edited` — explicit edits have been applied but recalculation has not
  completed;
- `recalculated` — edited proposal has been restaged and is paired with a new
  validation report.

Recalculation generates new deterministic plan/version hashes. Unchanged teeth
retain their source geometry and movement. The final stage is required to copy
the recalculated target setup exactly, as guaranteed by the existing staging
engine.

## Validation Behavior

The editing layer does not correct movements. If a doctor edit causes
geometric validation findings, the findings are returned in the recalculation
result and remain visible to the review UI. Clinical constraints are not
implemented and no movement is silently clipped, reduced, or rejected for
clinical reasons.

The current frontend has no real staged API payload yet. It therefore exposes
the same workflow against a clearly labeled engineering fixture and shows an
explicit real-data-unavailable state. This preview must not be treated as a
clinical plan.
