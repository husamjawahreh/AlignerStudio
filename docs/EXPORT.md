# Treatment Plan Export

**Phase 11 status:** Implemented deterministic, local engineering-package
export. It does not create a clinical approval, manufacturing file, or
patient-shareable artifact.

## Package

`TreatmentExportEngine` consumes immutable Phase 5/6/7/10 outputs and writes:

```text
export/
  manifest.json
  treatment-plan.json
  stages/stage-000.stl
  reports/movements.json
  reports/movements.csv
  reports/staging.json
  reports/validation.json
  reports/ipr.json
  reports/attachments.json
  reports/edit-history.json
  reports/provenance.json
export.zip
```

Each stage STL is a deterministic ASCII aggregation of its ordered tooth mesh
triangles. `stage-000.stl` represents immutable source geometry; the final
stage represents the immutable target setup exactly. No geometry is changed
while exporting.

## Audit Contract

The manifest records case, treatment-plan and version identifiers; staging and
validation hashes; software version; provenance; fixture/generated/
experimental/real status; explicitly supplied export timestamp; warnings; and
SHA-256 digests for every payload artifact. The manifest records its own
canonical-content digest excluding the digest field itself, because a file
cannot contain the SHA-256 value of its final byte representation without a
self-reference cycle.

With a caller-supplied timestamp, package JSON, STLs, file hashes, and ZIP
bytes are deterministic. ZIP entry timestamps are fixed. A generated current
timestamp is the only variable metadata when the caller does not supply one.

## Validation and Limits

Before writing, export validates plan/version ownership, contiguous stage
ordering, stable stage identifiers, mesh presence/index validity, Stage 0 and
final-stage geometry correspondence, validation stage references, proposal
references, and provenance. Missing data fails by default. Callers may opt
into a clearly marked `incomplete_engineering_export`, which retains the
validation warnings in all report envelopes.

Fixture exports are permitted only as engineering fixtures and are visibly
marked `fixture` in the manifest and reports. Proposal statuses remain review
states; acceptance in this data model is not clinical approval.

The current web workspace can request/download a labeled local export request,
but it does not yet invoke a service endpoint that returns the ZIP package.

## Excluded

- cloud storage or patient sharing;
- DICOM;
- manufacturing-specific aligner artifacts;
- external ML integration;
- clinical approval workflow or clinical decision logic.
