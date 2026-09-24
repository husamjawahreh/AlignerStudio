# P4 Biomechanics and Staging

## Scope

P4 represents geometric planning biomechanics and staged tooth movement. It is
not finite-element analysis, force simulation, clinical validation, or a
medical recommendation.

## Domain contracts

- `ToothMovement` carries translation, rotation, tip, torque,
  intrusion/extrusion, and lock/exclude state.
- `StageMovement` carries per-stage rate, accumulated movement, progress, and
  configured-limit status.
- `TreatmentStage` carries a stable label, stage type, validation findings,
  and metadata.
- `StagingConfiguration` accepts explicit stage count, macro/micro mode, and
  optional caller-supplied movement limits. No clinical limits are invented.

## Staging behavior

The existing deterministic source-to-target interpolation remains the only
staging engine. Stage 0 is the immutable original setup and the final stage is
the target setup. Intermediate stages linearly interpolate geometry and
movement. The API no longer hard-codes three stages: stage count and mode are
configured through `ALIGNERSTUDIO_STAGE_COUNT` and
`ALIGNERSTUDIO_STAGING_MODE`, with a minimum of two stages.

## Validation

The existing geometric validation engine runs for each stage. Its warnings,
errors, collision count, proximity count, and contact count are exposed in the
stage payload. The UI does not report a successful clinical result; it only
renders the geometric validator's actual state.

## Viewer

The stage timeline now uses stage labels and supports scrub/play/previous/next.
Selected-tooth inspection shows movement, stage rate, accumulated magnitude,
and configured-limit status. A movement-vector layer draws translation guides
from the actual tooth centroid to the staged translated position. These guides
are geometric annotations, not force vectors.

## Known limits

- Rotation and orthodontic dimensions remain the existing domain representation;
  no force or tissue model is present.
- Collision/proximity quality depends on the current mesh validator and its
  explicit caller-supplied thresholds.
- Locked/excluded state is represented in the contract; no automatic clinical
  correction is applied.
- Stage count is configuration, not a clinical recommendation.
