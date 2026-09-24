"""Truthful validation review summary — never invent PASS or overclaim checks."""

from __future__ import annotations

from dataclasses import dataclass

from domain.treatment_plan.setup import TreatmentPlanProposal
from domain.treatment_plan.staging import StagingResult
from domain.treatment_plan.validation import TreatmentValidationReport


@dataclass(frozen=True)
class ValidationReviewSummary:
    """Browser/API summary of what validation actually computed."""

    geometry: str
    contacts: str
    proximity: str
    collisions: str
    movement_constraints: str
    stage_consistency: str
    data_completeness: str
    provenance: str
    doctor_review: str
    findings: tuple[str, ...]

    def payload(self) -> dict[str, object]:
        return {
            "geometry": self.geometry,
            "contacts": self.contacts,
            "proximity": self.proximity,
            "collisions": self.collisions,
            "movementConstraints": self.movement_constraints,
            "stageConsistency": self.stage_consistency,
            "dataCompleteness": self.data_completeness,
            "provenance": self.provenance,
            "doctorReview": self.doctor_review,
            "findings": list(self.findings),
        }


def assess_stage_consistency(
    plan: TreatmentPlanProposal,
    staging: StagingResult,
    validation: TreatmentValidationReport,
) -> tuple[str, tuple[str, ...]]:
    """Return (status, findings) for stage consistency using export-grade checks."""
    findings: list[str] = []
    if not staging.stages:
        return "unavailable", ("Stage consistency unavailable: no stages present.",)
    expected = list(range(len(staging.stages)))
    actual = [stage.stage_index for stage in staging.stages]
    if actual != expected:
        findings.append("Stage indexes are not contiguous and ordered.")
    validation_ids = {result.stage_id for result in validation.stage_results}
    for stage in staging.stages:
        if not stage.stage_id:
            findings.append(f"Stage {stage.stage_index} has no stable ID.")
        elif stage.stage_id not in validation_ids:
            findings.append(f"Stage {stage.stage_index} is absent from validation results.")
    if plan.setup is not None and staging.stages:
        first = staging.stages[0]
        final = staging.stages[-1]

        def key(state) -> int | str:
            if state.tooth_number is not None:
                return state.tooth_number
            if state.tooth_ref:
                return state.tooth_ref
            raise ValueError("missing tooth identity")

        try:
            source = {key(item): item for item in plan.setup.source_states}
            target = {key(item): item for item in plan.setup.target_states}
            if {key(item) for item in first.tooth_states} != set(source):
                findings.append("Stage 0 tooth set does not match source setup.")
            if {key(item) for item in final.tooth_states} != set(target):
                findings.append("Final stage tooth set does not match target setup.")
            for state in first.tooth_states:
                identity = key(state)
                if state.vertices != source[identity].source_vertices:
                    findings.append(f"Stage 0 geometry differs from source for {identity}.")
            for state in final.tooth_states:
                identity = key(state)
                if state.vertices != target[identity].target_vertices:
                    findings.append(f"Final geometry differs from target for {identity}.")
        except ValueError as error:
            findings.append(f"Stage consistency identity gap: {error}")
    if findings:
        return "warning", tuple(findings)
    return "computed", ()


def assess_data_completeness(
    plan: TreatmentPlanProposal,
    staging: StagingResult,
    validation: TreatmentValidationReport,
) -> tuple[str, tuple[str, ...]]:
    findings: list[str] = []
    if plan.setup is None:
        findings.append("Treatment setup is missing.")
    if plan.limitations:
        findings.extend(plan.limitations)
    if not staging.stages:
        findings.append("Staging contains no stages.")
    if not validation.stage_results:
        findings.append("Validation report contains no stage results.")
    if findings:
        return "warning", tuple(findings)
    return "computed", ()


def assess_movement_constraints(staging: StagingResult) -> tuple[str, tuple[str, ...]]:
    """Movement constraints stay unavailable unless limits were actually configured."""
    if not staging.stages:
        return "unavailable", ("Movement constraints unavailable: no staged movements.",)
    statuses = {
        state.movement.limit_status
        for stage in staging.stages
        for state in stage.tooth_states
    }
    if statuses and statuses != {"not_configured"}:
        return "computed", ()
    return "unavailable", (
        "Movement constraints unavailable: no configured movement limits were applied.",
    )


def build_validation_review_summary(
    plan: TreatmentPlanProposal,
    staging: StagingResult,
    validation: TreatmentValidationReport,
) -> ValidationReviewSummary:
    """Build an honest summary from engines that actually ran."""
    geometry_ran = bool(validation.stage_results)
    geometry_status = "computed" if geometry_ran else "unavailable"
    stage_status, stage_findings = assess_stage_consistency(plan, staging, validation)
    completeness_status, completeness_findings = assess_data_completeness(
        plan, staging, validation
    )
    constraints_status, constraints_findings = assess_movement_constraints(staging)
    findings = (
        tuple(validation.warnings)
        + tuple(validation.errors)
        + stage_findings
        + completeness_findings
        + constraints_findings
    )
    return ValidationReviewSummary(
        geometry=geometry_status,
        contacts=geometry_status,
        proximity=geometry_status,
        collisions=geometry_status,
        movement_constraints=constraints_status,
        stage_consistency=stage_status,
        data_completeness=completeness_status,
        provenance="computed" if plan.provenance is not None else "unavailable",
        doctor_review="required",
        findings=findings,
    )
