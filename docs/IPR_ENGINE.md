# IPR Proposal Engine

**Phase 10 status:** Implemented as a deterministic, geometry-driven proposal
layer. It does not make a clinically valid IPR recommendation.

The engine compares source and target centroid relationships for adjacent,
same-quadrant identified teeth. It reports current distance, target distance,
a geometric space delta, proposed amount, confidence, status, and warnings.

All sites default to `needs_review`. If source/target geometry is unavailable,
malformed, or insufficient, the site becomes `unable_to_determine` rather than
being guessed. No maximum IPR value, clinical clearance, or treatment decision
is hard-coded. Any clinically relevant limit must be supplied by a future
external clinical configuration and documented in `CLINICAL_BOUNDARIES.md`.

IPR proposal identity is tied to the current treatment plan ID/version. When
the plan is recalculated, a new proposal result and deterministic proposal hash
are generated; prior proposal IDs are retained in history.
