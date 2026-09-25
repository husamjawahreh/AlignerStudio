# Movement / Tooth Interaction Engine (WP-04)

This package formalizes interaction contracts over the existing P4
``ToothMovement`` / ``DoctorMovementEdit`` pipeline.

- `interaction.py` — interaction phases, transform snapshots, constraint
  availability, edit reason normalization.
- Live transforms continue to flow through
  `engines.planning.editing.TreatmentEditingApplication` and
  `TreatmentPlanningEngine.rebuild_proposal` (source geometry never mutated).

Do **not** introduce a second transform/staging/validation system here.
