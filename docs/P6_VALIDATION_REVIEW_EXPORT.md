# P6 Validation, Clinical Review, and Export

## Validation workspace

The validation review now exposes explicit layers:

- geometry;
- contacts;
- proximity;
- collisions;
- movement constraints;
- stage consistency;
- data completeness; and
- doctor review status.

Geometry, contacts, proximity, collisions, and stage consistency are sourced
from the existing geometric validation engine. Movement constraints are marked
unavailable because no clinical limits are invented. Data completeness and
doctor review remain explicit review states. The UI avoids treating an
uncomputed or unavailable analysis as a generic PASS.

## IPR and attachments

IPR records expose tooth pair, current measurement, target measurement,
proposed amount, unit, stage, and review status. IPR remains a geometric
proposal and is never called prescribed.

Attachment records expose tooth, type, reference point, dimensions, stage,
status, and reason. When dimensions/geometry are unavailable, the API marks
the record as `generated: false` and the UI remains proposal/review-only. No
fake attachment mesh is rendered.

## Export

The existing deterministic export package preserves treatment plan metadata,
target setup, stages, movement reports, validation JSON, IPR, attachments,
doctor edit history, provenance, manifest hashes, and staged STL artifacts.
The Export workspace now summarizes stage count, validation state, proposal
review, doctor edits, and package contents. Export remains an auditable review
artifact and never implies clinical approval.

## Known limits

- The current geometry validator does not provide screen-space positions for
  individual collision/contact markers, so the UI reports counts/findings but
  does not fabricate marker coordinates.
- Clinical movement constraints are unavailable until a sourced/configured
  constraint system exists.
- Doctor review completion is represented as required; no automatic approval is
  possible.
