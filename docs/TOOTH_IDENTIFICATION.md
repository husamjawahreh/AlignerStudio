# Tooth Identification and Coordinate Systems

**Phase 4 status:** Implemented as a deterministic geometry-only engine. No
external ML model, clinical diagnostic rule, treatment plan, or staging logic
is included.

## Pipeline

```
ToothSegmentationResult
  → supplied arch context (upper/lower)
  → stable arch frame from segmented centroids
  → geometric slot validation
  → FDI identity when all rules pass
  → local coordinate frame + descriptive landmarks
```

Segmentation and identification are separate contracts. A
`ToothInstance` has mesh geometry and a stable segmentation ID only. It does
not contain an FDI label. `ToothIdentificationEngine` is the only Phase 4
component that can create `FDIToothIdentity` values.

## Identification Rules

The engine requires the caller to provide `upper` or `lower`; arch type is not
inferred from arbitrary mesh ordering. The following deterministic rules are
applied:

1. Every candidate must contain finite vertices and valid local triangle
   indices. Invalid geometry becomes `unidentified` with no FDI identity.
2. The valid centroids define an arch frame. The lateral axis is the largest
   principal direction, oriented deterministically toward the positive global
   X direction. The vertical axis is the smallest principal direction,
   oriented toward positive global Z; the remaining axis is their cross
   product.
3. A complete arch must contain exactly sixteen valid instances: eight on
   the negative lateral side and eight on the positive side.
4. Each side is ordered by absolute lateral distance from the centerline,
   from the midline outward. The slots map to positions 1 through 8.
5. Negative lateral positions map to patient-right quadrants (`1` upper,
   `4` lower); positive positions map to patient-left quadrants (`2` upper,
   `3` lower).
6. Any incomplete, duplicate, or centerline-ambiguous slot set remains
   `uncertain` and receives no FDI label. No missing tooth is silently shifted
   into a neighboring FDI position.

The slot completeness and ambiguity values are engineering validity rules,
not diagnostic or treatment thresholds. See
[CLINICAL_BOUNDARIES.md](../CLINICAL_BOUNDARIES.md).

## Status Values

- `identified`: all geometric rules passed and an FDI identity was assigned.
- `uncertain`: geometry exists, but arch completeness or slot uniqueness is
  insufficient for a defensible FDI assignment.
- `unidentified`: geometry is missing or malformed and no identity can be
  computed.

Confidence is geometric run confidence only. It is never clinical confidence
and never means treatment suitability or approval.

## Phase 13 Real-Case Gate

For an uploaded STL, the API invokes identification only after a configured
external segmentation model passes its artifact and contract checks. The
per-case diagnostic reports segmentation runtime, instance count, mean
geometric identification confidence, identified/uncertain/unidentified counts,
and failures. Incomplete identification blocks planning; it never receives a
fixture identity or an inferred replacement tooth.

## Coordinate System

Every identified tooth receives a stable orthonormal frame:

- `origin`: segmented tooth centroid.
- `lateral_axis`: mesiodistal/lateral direction.
- `anterior_axis`: buccolingual/anterior direction.
- `vertical_axis`: occlusogingival/vertical direction.

The typed frame is deliberately suitable for future translation, rotation,
tip, torque, intrusion, and extrusion values. Phase 4 does not apply any
movement.

Descriptive landmarks include centroid, mesial point, distal point, occlusal
point, and gingival point. They are extrema of the supplied surface geometry,
not anatomical or clinical diagnoses.
