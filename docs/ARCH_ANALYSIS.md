# Initial Arch Analysis

**Phase 4 status:** Implemented as descriptive geometry only. It does not
diagnose malocclusion, evaluate treatment suitability, or apply clinical
thresholds.

## Inputs

`ArchAnalysisEngine` consumes `ToothIdentificationResult` and analyzes only
teeth with `identified` status. Uncertain and unidentified instances remain
visible in the identification result but are excluded from measurements that
require a trusted FDI identity.

## Outputs

`ArchMeasurements` contains:

- `centerline`: ordered centroid points representing the observed arch path.
- `ordered_instance_ids`: lateral mesh order from patient-right to
  patient-left.
- `total_width`: lateral distance between the outermost identified centroids.
- `left_half_width` and `right_half_width`: centerline-to-outermost lateral
  spans.
- `anterior_width`: distance between identified central incisors when both are
  available.
- `posterior_width`: distance between identified second molars when both are
  available.
- `consecutive_tooth_distances`: Euclidean distances between neighboring
  ordered centroids.
- `anterior_to_posterior_order`: instances ordered by distance from the
  centerline outward.
- provenance, fixture status, and an explicit descriptive-geometry note.

Missing required teeth produce `None` for the corresponding named width; the
engine does not interpolate or invent measurements. Fewer than two identified
teeth raises an explicit analysis error.

## Coordinate and Ordering Rules

The same deterministic principal-axis frame used by identification is rebuilt
from identified centroids. The largest variance direction is lateral, with a
stable global-axis sign convention. The smallest variance direction is
vertical, and the cross product completes the orthogonal frame. Neighbor order
is the sorted projection on the lateral axis, not segmentation instance ID or
arbitrary file order.

## Clinical Boundary

All values are geometric descriptions of the provided mesh. No value is a
clinical limit, diagnosis, movement recommendation, or approval signal. Future
arch-form or treatment rules must be documented separately in
[CLINICAL_BOUNDARIES.md](../CLINICAL_BOUNDARIES.md) before implementation.

The test fixture in `tests/fixtures/synthetic_arch.py` contains simple
cuboids arranged on a mathematical curve. It is engineering-only data and is
not representative of dental anatomy.
