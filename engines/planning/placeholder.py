"""Placeholder planning engine.

Produces a single-stage treatment plan equal to the initial tooth
positions. Does NOT perform arch analysis, setup generation, or staging.
Always tagged `generated` + `fixture=True`. See TREATMENT_PLAN.md.
"""

from __future__ import annotations

from domain.case.provenance import DataProvenance
from domain.treatment_plan.models import Stage, ToothPosition, TreatmentPlan

FIXTURE_NOTE = (
    "Planning engine not yet implemented; returns a single fixture stage "
    "equal to the initial tooth positions. Not a clinically valid setup."
)


class PlaceholderPlanningEngine:
    """Fixture implementation of :class:`PlanningEngine`."""

    def generate_plan(
        self, case_id: str, tooth_positions: tuple[ToothPosition, ...]
    ) -> TreatmentPlan:
        stage = Stage(
            index=0,
            tooth_positions=tooth_positions,
            provenance=DataProvenance.GENERATED,
            fixture=True,
            notes=FIXTURE_NOTE,
        )
        return TreatmentPlan(
            case_id=case_id,
            stages=(stage,),
            provenance=DataProvenance.GENERATED,
            fixture=True,
            notes=FIXTURE_NOTE,
        )
