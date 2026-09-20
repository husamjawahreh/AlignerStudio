# Clinical Boundaries

This document tracks every clinically-relevant threshold, rule, or
assumption used in the codebase, its source, and its confidence level. It
must be updated whenever a new threshold is introduced. **Never hard-code a
clinical number without an entry here.**

## Rule Catalog

| ID       | Description                                                         | Value                                                       | Source                                                                                                                                            | Status                                                                 | Location                                |
| -------- | ------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | --------------------------------------- |
| MESH-001 | Minimum triangle count for a usable arch scan                       | 1,000 triangles                                             | Engineering heuristic (not clinical), chosen to reject empty/corrupt files only                                                                   | Provisional — **not a clinical threshold**, purely a file-sanity check | `engines/geometry/mesh_validation.py`   |
| MESH-002 | Mesh must load as a valid triangle mesh (readable, non-empty)       | boolean                                                     | File-format requirement                                                                                                                           | Provisional                                                            | `engines/geometry/mesh_validation.py`   |
| MESH-003 | Watertightness / open-boundary check reported to user               | boolean, informational only (does not block Phase 1 upload) | Common practice in dental mesh processing literature (e.g. discussed in MeshSegNet preprocessing) — **not a specific numeric clinical guideline** | Provisional — informational flag only, no clinical claim attached      | `engines/geometry/mesh_validation.py`   |
| GEO-001  | Complete geometric arch slot count required before FDI assignment   | 16 valid instances, 8 per lateral side                      | Engineering/data-integrity rule for deterministic identification; not a clinical or diagnostic threshold                                          | Provisional — prevents guessed labels on incomplete geometry           | `engines/arrangement/identification.py` |
| GEO-002  | Lateral ambiguity tolerance for centerline/duplicate-slot detection | `1e-6` coordinate units                                     | Numerical comparison tolerance only; not a clinical measurement                                                                                   | Provisional — engineering precision setting                            | `engines/arrangement/identification.py` |

No clinical diagnostic or treatment thresholds were added in Phase 4, Phase 5,
Phase 6, Phase 7, Phase 10, or Phase 11. Arch widths, distances, PCA axes, slot counts, confidence
values, objective movement requests, transformed target geometry, stage
interpolation, caller-supplied geometric proximity/contact/collision
thresholds, plan/report hashes, and export integrity checks are descriptive
geometry, explicit user inputs, or engineering metadata only. Treatment setup
generation, staging, geometric validation, adjunct proposals, and export do
not decide whether a movement is safe or appropriate. Clinical movement
limits, IPR limits, attachment specifications, and anatomical constraints are
still **not implemented**.

Phase 12's API engineering demo uses only existing fixture interpolation and
geometric-validation configuration values. These are deterministic engineering
test inputs, not clinical thresholds, and real uploaded cases do not use them
as a fallback for unavailable segmentation.
When they are implemented, each numeric threshold (e.g. maximum staged movement per
aligner in mm/degrees, minimum interproximal clearance) must have its own
row citing a peer-reviewed source, a named clinical advisor, or an explicit
"placeholder — needs clinical sign-off" status before merging.

## Rules for Contributors

1. Never introduce a numeric clinical threshold without adding a row here
   in the same change.
2. If the source is unknown or unavailable, mark `Status` as **"needs
   clinical sign-off"** and keep the code path gated so it cannot be
   presented as clinically approved (see `DataProvenance`).
3. Engineering/file-sanity thresholds (like `MESH-001`) must be explicitly
   labeled as non-clinical to avoid being mistaken for medical guidance.
4. Any change to a value in this table requires updating both the code and
   this document in the same commit.
