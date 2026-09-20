# Geometric Validation Engine

**Phase 7 status:** Implemented real mesh-based geometric validation for staged
treatment plans. No clinical interpretation or automatic plan correction is
performed.

## Pipeline

```
StagingResult
  → caller-supplied geometric thresholds
  → stage/tooth mesh validation
  → AABB broad-phase filtering
  → triangle-level surface distance/intersection checks
  → proximity, collision, and contact results
  → per-tooth results
  → per-stage results
  → deterministic treatment validation report
```

## Configuration

`GeometricValidationConfiguration` requires the caller to provide:

- `proximity_threshold` — maximum surface distance for a proximity result;
- `contact_tolerance` — distance at or below which a pair is reported as
  contact;
- `collision_tolerance` — positive volumetric overlap tolerance for classifying
  an intersection;
- `engine_version` — explicit engine identity used in deterministic context.

There are no default geometric or clinical thresholds. The values are caller
configuration and must be recorded by the application that invokes the engine.
They are not diagnostic limits, movement limits, or treatment recommendations.

## Results

- `ProximityResult`: stage, tooth pair, measured surface distance, configured
  threshold, status, provenance, stable result ID.
- `CollisionResult`: stage, tooth pair, intersection flag, measured overlap
  depth when available, tolerance, status, provenance, stable result ID.
- `ContactResult`: stage, tooth pair, contact flag, measured surface distance,
  tolerance, status, provenance, stable result ID.
- `ToothValidationResult`: all pair findings involving one tooth.
- `StageValidationResult`: all pair findings and tooth results for one stage.
- `TreatmentValidationReport`: all stage results, overall status, report ID,
  provenance, fixture state, warnings, and errors.

Statuses are geometric validation states: `pass`, `warning`, `error`, and
`invalid`. They do not mean clinically safe, unsafe, approved, or ready.

## Geometry and Performance

Each staged state carries immutable local vertices and faces. The engine builds
`trimesh.Trimesh` objects with `process=False`, validates finite coordinates,
face shape/index validity, and rejects empty or degenerate geometry without
crashing.

Pair evaluation is deterministic:

1. states are sorted by tooth number;
2. invalid meshes are reported and skipped from pair calculations;
3. mesh AABBs are checked first;
4. only candidate pairs within the maximum configured threshold are passed to
   triangle-level checks;
5. triangle distances use point-triangle and edge-edge distance calculations;
6. surface intersections are checked by segment-triangle tests;
7. touching surfaces are reported as contacts, while positive measured overlap
   beyond the collision tolerance is reported as a collision.

The broad phase is a conservative performance filter, not a clinical
approximation. It never changes source or target geometry and does not modify
movements.

## Hook Integration

`GeometricValidationEngine.detect()` implements the existing stage collision
validation hook shape and returns `ValidationFinding` values. Additional stage
hook protocols remain available for future movement limits, contact policies,
and anatomical/clinical constraints. Phase 7 does not implement those rules.

## Provenance and Immutability

Report provenance and fixture state are inherited from the staged treatment
result. Validation never upgrades provenance to `clinically_reviewed`. Source
vertices, target vertices, stage states, and treatment proposals remain
unchanged. A validation finding cannot automatically restage or edit a plan.

## Engineering Fixtures

`tests/fixtures/synthetic_validation.py` provides deterministic cuboid meshes
for separated, touching, intersecting, and multiple independent tooth pairs.
Malformed empty geometry is also tested. These are engineering fixtures only,
not dental scans or clinical evidence.
