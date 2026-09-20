"""Planning engine interface.

Real implementations (e.g. wrapping TANet via `adapters/tanet`) must
implement this `Protocol`. See REUSE_MATRIX.md before adding a real
adapter-backed implementation.
"""

from __future__ import annotations

from typing import Protocol

from domain.treatment_plan.models import ToothPosition, TreatmentPlan


class PlanningEngine(Protocol):
    """Generates a treatment plan (staged tooth movements) for a case."""

    def generate_plan(
        self, case_id: str, tooth_positions: tuple[ToothPosition, ...]
    ) -> TreatmentPlan:
        """Return a treatment plan for the given case and initial teeth."""
        ...
