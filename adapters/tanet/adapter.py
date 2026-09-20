"""Adapter boundary for TANet (tooth arrangement / automatic setup network).

Not integrated in Phase 1 — see REUSE_MATRIX.md.
"""

from __future__ import annotations

from domain.treatment_plan.models import ToothPosition, TreatmentPlan


class TANetAdapter:
    """Adapter stub for TANet. Not implemented — see REUSE_MATRIX.md."""

    def generate_plan(
        self, case_id: str, tooth_positions: tuple[ToothPosition, ...]
    ) -> TreatmentPlan:
        raise NotImplementedError(
            "TANet is not integrated yet. See REUSE_MATRIX.md before implementing."
        )
