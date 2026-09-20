# Attachment Proposals

**Phase 10 status:** Implemented as deterministic objective/geometry-driven
proposal metadata. No attachment shape generation or clinical validation is
implemented.

The engine creates candidates for teeth with explicit angular movement. Each
candidate records tooth ID, undetermined attachment type when no validated
shape algorithm exists, a reference point, coordinate-frame orientation,
missing dimensions, reason, confidence, status, provenance, and warnings.
Candidates default to `needs_review` and are never accepted automatically.

Attachment proposals are associated with the current treatment plan ID and
version. Recalculation generates a new deterministic proposal ID and retains
previous proposal IDs in history. Invalid or unavailable target geometry
returns an explicit unable-to-determine state.

Doctor status changes are explicit (`doctor_modified`, `accepted`, or
`rejected`) and do not alter tooth movements. The UI displays every warning and
keeps fixture proposals visibly labeled as fixtures.
