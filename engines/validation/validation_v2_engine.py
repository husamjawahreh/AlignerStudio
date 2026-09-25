"""WP-09 Validation 2.0 engine — honesty/view layer over GeometricValidationEngine.

Does not replace geometric validation. Does not invent clinical findings or approval.
Unavailable capability checks remain explicitly NOT_AVAILABLE.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from domain.treatment_plan.setup import TreatmentPlanProposal
from domain.treatment_plan.staging import StagingResult
from domain.treatment_plan.validation import (
    TreatmentValidationReport,
    ValidationStatus,
)
from domain.treatment_plan.validation_v2 import (
    VALIDATION_ALGORITHM_ID,
    VALIDATION_ALGORITHM_VERSION,
    VALIDATION_CONTRACT_VERSION,
    ValidationBinding,
    ValidationCategory,
    ValidationCheckState,
    ValidationCheckSummary,
    ValidationContextKind,
    ValidationFinding,
    ValidationFreshness,
    ValidationRun,
    ValidationRunSummary,
    ValidationSeverity,
    ValidationThresholdRecord,
    ValidationTruthState,
    evaluate_validation_freshness,
)
from engines.validation.geometric_engine import GeometricValidationConfiguration
from engines.validation.review_summary import build_validation_review_summary


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _run_id(
    *,
    case_id: str,
    report_id: str | None,
    setup_version_id: str | None,
    staging_version_id: str | None,
) -> str:
    material = f"{case_id}|{report_id}|{setup_version_id}|{staging_version_id}|{VALIDATION_CONTRACT_VERSION}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def _config_hash(configuration: GeometricValidationConfiguration | None) -> str | None:
    if configuration is None:
        return None
    material = (
        f"{configuration.proximity_threshold}|"
        f"{configuration.contact_tolerance}|"
        f"{configuration.collision_tolerance}|"
        f"{configuration.engine_version}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _map_geometric_status(status: ValidationStatus) -> ValidationCheckState:
    if status is ValidationStatus.PASS:
        return ValidationCheckState.PASS
    if status is ValidationStatus.WARNING:
        return ValidationCheckState.WARNING
    if status is ValidationStatus.ERROR:
        return ValidationCheckState.ERROR
    return ValidationCheckState.INVALID


def _severity_for_check(state: ValidationCheckState) -> ValidationSeverity:
    if state in (ValidationCheckState.ERROR, ValidationCheckState.INVALID):
        return ValidationSeverity.ERROR
    if state in (ValidationCheckState.WARNING, ValidationCheckState.REQUIRES_REVIEW):
        return ValidationSeverity.WARNING
    return ValidationSeverity.INFO


def _threshold(
    name: str,
    value: float | None,
    *,
    engine_version: str,
) -> ValidationThresholdRecord:
    return ValidationThresholdRecord(
        name=name,
        value=value,
        unit="model units",
        kind="technical",
        version=engine_version,
        source="GeometricValidationConfiguration",
    )


def _unavailable_check(
    *,
    check_id: str,
    category: ValidationCategory,
    label: str,
    reason: str,
    context_kind: ValidationContextKind = ValidationContextKind.CASE,
) -> tuple[ValidationCheckSummary, ValidationFinding]:
    check = ValidationCheckSummary(
        check_id=check_id,
        category=category,
        label=label,
        check_state=ValidationCheckState.NOT_AVAILABLE,
        truth_state=ValidationTruthState.NOT_AVAILABLE,
        context_kind=context_kind,
        finding_count=1,
        limitations=(reason,),
    )
    finding = ValidationFinding(
        finding_id=f"na-{check_id}",
        category=category,
        severity=ValidationSeverity.INFO,
        check_state=ValidationCheckState.NOT_AVAILABLE,
        truth_state=ValidationTruthState.NOT_AVAILABLE,
        affected_tooth_refs=(),
        arch=None,
        stage_index=None,
        context_kind=context_kind,
        measured_value=None,
        measured_unit=None,
        threshold=None,
        source="capability_gate",
        algorithm=VALIDATION_ALGORITHM_ID,
        algorithm_version=VALIDATION_ALGORITHM_VERSION,
        message=reason,
        review_state="not_applicable",
        provenance="experimental",
        limitations=(reason, "Unavailable checks are never treated as PASS."),
        spatial_binding=None,
    )
    return check, finding


def _findings_from_geometric(
    validation: TreatmentValidationReport,
    *,
    engine_version: str,
    proximity_threshold: float,
    contact_tolerance: float,
    collision_tolerance: float,
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for stage in validation.stage_results:
        context = ValidationContextKind.STAGE
        for item in stage.collision_results:
            if not item.intersects and item.status is ValidationStatus.PASS:
                continue
            findings.append(
                ValidationFinding(
                    finding_id=item.result_id,
                    category=ValidationCategory.COLLISION,
                    severity=_severity_for_check(_map_geometric_status(item.status)),
                    check_state=_map_geometric_status(item.status),
                    truth_state=ValidationTruthState.COMPUTED,
                    affected_tooth_refs=(item.tooth_a, item.tooth_b),
                    arch=None,
                    stage_index=item.stage_index,
                    context_kind=context,
                    measured_value=item.measured_depth,
                    measured_unit="model units",
                    threshold=_threshold(
                        "collision_tolerance",
                        collision_tolerance,
                        engine_version=engine_version,
                    ),
                    source="GeometricValidationEngine",
                    algorithm="GeometricValidationEngine",
                    algorithm_version=engine_version,
                    message=(
                        f"Geometric collision finding for {item.tooth_a}/{item.tooth_b} "
                        f"at stage {item.stage_index}."
                    ),
                    review_state="requires_review",
                    provenance=item.provenance.value,
                    limitations=(
                        "Geometric collision is not a clinical diagnosis.",
                        "PASS/WARNING/ERROR are technical states only.",
                    ),
                    spatial_binding={
                        "kind": "tooth_pair",
                        "tooth_a": item.tooth_a,
                        "tooth_b": item.tooth_b,
                        "stage_index": item.stage_index,
                    },
                )
            )
        for item in stage.proximity_results:
            if item.status is ValidationStatus.PASS:
                continue
            findings.append(
                ValidationFinding(
                    finding_id=item.result_id,
                    category=ValidationCategory.PROXIMITY,
                    severity=_severity_for_check(_map_geometric_status(item.status)),
                    check_state=_map_geometric_status(item.status),
                    truth_state=ValidationTruthState.COMPUTED,
                    affected_tooth_refs=(item.tooth_a, item.tooth_b),
                    arch=None,
                    stage_index=item.stage_index,
                    context_kind=context,
                    measured_value=item.measured_distance,
                    measured_unit="model units",
                    threshold=_threshold(
                        "proximity_threshold",
                        proximity_threshold,
                        engine_version=engine_version,
                    ),
                    source="GeometricValidationEngine",
                    algorithm="GeometricValidationEngine",
                    algorithm_version=engine_version,
                    message=(
                        f"Geometric proximity finding for {item.tooth_a}/{item.tooth_b} "
                        f"at stage {item.stage_index}."
                    ),
                    review_state="requires_review",
                    provenance=item.provenance.value,
                    limitations=(
                        "Geometric proximity is not a clinical occlusal diagnosis.",
                    ),
                    spatial_binding={
                        "kind": "tooth_pair",
                        "tooth_a": item.tooth_a,
                        "tooth_b": item.tooth_b,
                        "stage_index": item.stage_index,
                    },
                )
            )
        for item in stage.contact_results:
            if not item.is_contact and item.status is ValidationStatus.PASS:
                continue
            findings.append(
                ValidationFinding(
                    finding_id=item.result_id,
                    category=ValidationCategory.CONTACT,
                    severity=_severity_for_check(_map_geometric_status(item.status)),
                    check_state=_map_geometric_status(item.status),
                    truth_state=ValidationTruthState.COMPUTED,
                    affected_tooth_refs=(item.tooth_a, item.tooth_b),
                    arch=None,
                    stage_index=item.stage_index,
                    context_kind=context,
                    measured_value=item.measured_distance,
                    measured_unit="model units",
                    threshold=_threshold(
                        "contact_tolerance",
                        contact_tolerance,
                        engine_version=engine_version,
                    ),
                    source="GeometricValidationEngine",
                    algorithm="GeometricValidationEngine",
                    algorithm_version=engine_version,
                    message=(
                        f"Geometric contact finding for {item.tooth_a}/{item.tooth_b} "
                        f"at stage {item.stage_index}."
                    ),
                    review_state="requires_review",
                    provenance=item.provenance.value,
                    limitations=(
                        "Intra-arch geometric contact is not a clinical occlusal contact.",
                    ),
                    spatial_binding={
                        "kind": "tooth_pair",
                        "tooth_a": item.tooth_a,
                        "tooth_b": item.tooth_b,
                        "stage_index": item.stage_index,
                    },
                )
            )
    return findings


def build_validation_run(
    *,
    case_id: str,
    proposal: TreatmentPlanProposal,
    staging: StagingResult,
    validation: TreatmentValidationReport | None,
    configuration: GeometricValidationConfiguration | None = None,
    setup_version_id: str | None = None,
    staging_version_id: str | None = None,
    clinical_tools_setup_version_id: str | None = None,
    clinical_tools_staging_version_id: str | None = None,
    current_setup_version_id: str | None = None,
    current_staging_version_id: str | None = None,
    current_clinical_tools_setup_version_id: str | None = None,
    current_clinical_tools_staging_version_id: str | None = None,
    occlusion_capability_state: str | None = None,
    occlusion_registration_version_id: str | None = None,
    root_geometry_state: str | None = None,
    clinical_axes_state: str | None = None,
    landmark_state: str | None = None,
    manufacturing_ready: bool = False,
    input_hash: str | None = None,
    upper_mesh_hash: str | None = None,
    lower_mesh_hash: str | None = None,
    previous_run: ValidationRun | None = None,
    generated_at: str | None = None,
) -> ValidationRun:
    """Build Validation 2.0 run from existing geometric report + capability gates."""
    started = perf_counter()
    generated_at = generated_at or _now()
    engine_version = (
        configuration.engine_version if configuration is not None else "phase7-geometric-validation-1"
    )
    proximity_threshold = configuration.proximity_threshold if configuration else None
    contact_tolerance = configuration.contact_tolerance if configuration else None
    collision_tolerance = configuration.collision_tolerance if configuration else None

    checks: list[ValidationCheckSummary] = []
    findings: list[ValidationFinding] = []
    thresholds: list[ValidationThresholdRecord] = []

    if configuration is not None:
        thresholds.extend(
            [
                _threshold("proximity_threshold", proximity_threshold, engine_version=engine_version),
                _threshold("contact_tolerance", contact_tolerance, engine_version=engine_version),
                _threshold("collision_tolerance", collision_tolerance, engine_version=engine_version),
            ]
        )

    legacy = None
    geometric_status = ValidationCheckState.NOT_AVAILABLE
    if validation is not None and validation.stage_results:
        geom_started = perf_counter()
        legacy = build_validation_review_summary(proposal, staging, validation).payload()
        geometric_findings = _findings_from_geometric(
            validation,
            engine_version=engine_version,
            proximity_threshold=float(proximity_threshold or 0.0),
            contact_tolerance=float(contact_tolerance or 0.0),
            collision_tolerance=float(collision_tolerance or 0.0),
        )
        findings.extend(geometric_findings)
        geometric_status = _map_geometric_status(validation.status)
        # Geometric category checks — PASS means technical no-finding, still requires doctor review.
        for category, label, count_attr in (
            (ValidationCategory.COLLISION, "Intra-arch collisions", "collision"),
            (ValidationCategory.PROXIMITY, "Intra-arch proximity", "proximity"),
            (ValidationCategory.CONTACT, "Intra-arch contacts", "contact"),
        ):
            cat_findings = [f for f in geometric_findings if f.category is category]
            if cat_findings:
                worst = ValidationCheckState.PASS
                for item in cat_findings:
                    if item.check_state is ValidationCheckState.ERROR:
                        worst = ValidationCheckState.ERROR
                        break
                    if item.check_state is ValidationCheckState.WARNING:
                        worst = ValidationCheckState.WARNING
                    elif item.check_state is ValidationCheckState.INVALID:
                        worst = ValidationCheckState.INVALID
                state = worst
            else:
                state = ValidationCheckState.PASS
            checks.append(
                ValidationCheckSummary(
                    check_id=f"geometric_{category.value}",
                    category=category,
                    label=label,
                    check_state=state,
                    truth_state=ValidationTruthState.COMPUTED,
                    context_kind=ValidationContextKind.STAGE,
                    finding_count=len(cat_findings),
                    limitations=(
                        "Technical geometric check only — not clinical approval.",
                        "Cross-arch pairs are excluded by GeometricValidationEngine design.",
                    ),
                )
            )
        # Geometry / data quality from stage result presence
        checks.append(
            ValidationCheckSummary(
                check_id="geometry_data_quality",
                category=ValidationCategory.GEOMETRY_DATA_QUALITY,
                label="Geometry / data quality",
                check_state=geometric_status
                if geometric_status is not ValidationCheckState.PASS
                else ValidationCheckState.PASS,
                truth_state=ValidationTruthState.COMPUTED,
                context_kind=ValidationContextKind.CASE,
                finding_count=len(validation.errors) + len(validation.warnings),
                limitations=("Mesh/stage geometric quality signals only.",),
            )
        )
        # Stage consistency from legacy summary
        stage_state_raw = (legacy or {}).get("stageConsistency", "unavailable")
        if stage_state_raw == "computed":
            stage_check_state = ValidationCheckState.PASS
            stage_truth = ValidationTruthState.COMPUTED
        elif stage_state_raw == "warning":
            stage_check_state = ValidationCheckState.WARNING
            stage_truth = ValidationTruthState.REQUIRES_REVIEW
        else:
            stage_check_state = ValidationCheckState.NOT_AVAILABLE
            stage_truth = ValidationTruthState.NOT_AVAILABLE
        checks.append(
            ValidationCheckSummary(
                check_id="staging_consistency",
                category=ValidationCategory.STAGING_CONSISTENCY,
                label="Staging consistency",
                check_state=stage_check_state,
                truth_state=stage_truth,
                context_kind=ValidationContextKind.STAGE,
                finding_count=0,
                limitations=("Export-grade stage/setup geometry consistency.",),
            )
        )
        source_check_state = stage_check_state
        checks.append(
            ValidationCheckSummary(
                check_id="source_target_consistency",
                category=ValidationCategory.SOURCE_CONSISTENCY,
                label="Source / target consistency",
                check_state=source_check_state,
                truth_state=stage_truth,
                context_kind=ValidationContextKind.SOURCE,
                finding_count=0,
                limitations=("First/final stage must match source/target setup when checkable.",),
            )
        )
        checks.append(
            ValidationCheckSummary(
                check_id="treatment_state_consistency",
                category=ValidationCategory.TREATMENT_STATE_CONSISTENCY,
                label="Treatment state consistency",
                check_state=source_check_state,
                truth_state=stage_truth,
                context_kind=ValidationContextKind.TARGET,
                finding_count=0,
                limitations=("Setup/staging identity consistency only.",),
            )
        )
        _ = geom_started
    else:
        check, finding = _unavailable_check(
            check_id="geometric_collision",
            category=ValidationCategory.COLLISION,
            label="Intra-arch collisions",
            reason="Geometric validation report is unavailable.",
            context_kind=ValidationContextKind.STAGE,
        )
        checks.append(check)
        findings.append(finding)
        for category, label in (
            (ValidationCategory.PROXIMITY, "Intra-arch proximity"),
            (ValidationCategory.CONTACT, "Intra-arch contacts"),
            (ValidationCategory.GEOMETRY_DATA_QUALITY, "Geometry / data quality"),
        ):
            c, f = _unavailable_check(
                check_id=f"geometric_{category.value}",
                category=category,
                label=label,
                reason="Geometric validation report is unavailable.",
            )
            checks.append(c)
            findings.append(f)

    # Movement constraints — reuse P5 honesty
    if validation is not None:
        constraints_status = (legacy or {}).get("movementConstraints", "unavailable")
        if constraints_status == "unavailable":
            c, f = _unavailable_check(
                check_id="movement_constraints",
                category=ValidationCategory.MOVEMENT_CONSTRAINTS,
                label="Movement constraints",
                reason="Movement constraints unavailable: no configured movement limits were applied.",
            )
            checks.append(c)
            findings.append(f)
        else:
            checks.append(
                ValidationCheckSummary(
                    check_id="movement_constraints",
                    category=ValidationCategory.MOVEMENT_CONSTRAINTS,
                    label="Movement constraints",
                    check_state=ValidationCheckState.PASS,
                    truth_state=ValidationTruthState.COMPUTED,
                    context_kind=ValidationContextKind.STAGE,
                    finding_count=0,
                    limitations=("Configured movement limit signals only.",),
                )
            )
    else:
        c, f = _unavailable_check(
            check_id="movement_constraints",
            category=ValidationCategory.MOVEMENT_CONSTRAINTS,
            label="Movement constraints",
            reason="Movement constraints unavailable without a validation report.",
        )
        checks.append(c)
        findings.append(f)

    # Clinical tools consistency — presence of binding, not clinical IPR approval
    if clinical_tools_setup_version_id:
        stale_tools = (
            current_clinical_tools_setup_version_id
            and clinical_tools_setup_version_id != current_clinical_tools_setup_version_id
        ) or (
            clinical_tools_staging_version_id
            and current_clinical_tools_staging_version_id
            and clinical_tools_staging_version_id != current_clinical_tools_staging_version_id
        )
        checks.append(
            ValidationCheckSummary(
                check_id="clinical_tool_consistency",
                category=ValidationCategory.CLINICAL_TOOL_CONSISTENCY,
                label="Clinical tool consistency",
                check_state=(
                    ValidationCheckState.REQUIRES_REVIEW
                    if stale_tools
                    else ValidationCheckState.REQUIRES_REVIEW
                ),
                truth_state=ValidationTruthState.REQUIRES_REVIEW,
                context_kind=ValidationContextKind.CLINICAL_TOOLS,
                finding_count=0,
                limitations=(
                    "Clinical tools require doctor review; geometric validation does not approve IPR/attachments.",
                ),
            )
        )
    else:
        c, f = _unavailable_check(
            check_id="clinical_tool_consistency",
            category=ValidationCategory.CLINICAL_TOOL_CONSISTENCY,
            label="Clinical tool consistency",
            reason="Clinical tools binding is not available for this validation context.",
            context_kind=ValidationContextKind.CLINICAL_TOOLS,
        )
        checks.append(c)
        findings.append(f)

    # Occlusion-dependent checks — NEVER PASS when occlusion unavailable
    occ_state = (occlusion_capability_state or "unavailable").lower()
    if occ_state in ("unavailable", "not_available", ""):
        c, f = _unavailable_check(
            check_id="occlusion_capability",
            category=ValidationCategory.OCCLUSION_CAPABILITY,
            label="Occlusion capability",
            reason=(
                "Occlusion-dependent validation is not available without genuine "
                "bite/registration evidence."
            ),
        )
        checks.append(c)
        findings.append(f)
    elif occ_state in ("requires_review", "source_registered", "computed"):
        checks.append(
            ValidationCheckSummary(
                check_id="occlusion_capability",
                category=ValidationCategory.OCCLUSION_CAPABILITY,
                label="Occlusion capability",
                check_state=ValidationCheckState.REQUIRES_REVIEW,
                truth_state=ValidationTruthState.REQUIRES_REVIEW,
                context_kind=ValidationContextKind.CASE,
                finding_count=0,
                limitations=(
                    "Occlusion capability present but not clinically validated.",
                    "Geometric proximity is not a clinical occlusal diagnosis.",
                ),
            )
        )
    else:
        checks.append(
            ValidationCheckSummary(
                check_id="occlusion_capability",
                category=ValidationCategory.OCCLUSION_CAPABILITY,
                label="Occlusion capability",
                check_state=ValidationCheckState.REQUIRES_REVIEW,
                truth_state=ValidationTruthState.REQUIRES_REVIEW,
                context_kind=ValidationContextKind.CASE,
                finding_count=0,
                limitations=("Occlusion state requires doctor review.",),
            )
        )

    # Root / clinical axes / landmarks — capability gates from WP-08
    for state_value, category, check_id, label, reason in (
        (
            root_geometry_state,
            ValidationCategory.ROOT_ANATOMY,
            "root_anatomy",
            "Root anatomy checks",
            "Root-anatomy validation is not available for crown-only STL.",
        ),
        (
            clinical_axes_state,
            ValidationCategory.CLINICAL_AXES,
            "clinical_axes",
            "Clinical dental axes checks",
            "Clinical-axis validation is not available; mesh PCA is not a clinical axis.",
        ),
        (
            landmark_state,
            ValidationCategory.LANDMARKS,
            "landmarks",
            "Landmark checks",
            "Landmark validation is not available without genuine landmark evidence.",
        ),
    ):
        normalized = (state_value or "not_available").lower()
        if normalized in ("not_available", "unavailable", ""):
            c, f = _unavailable_check(
                check_id=check_id,
                category=category,
                label=label,
                reason=reason,
            )
            checks.append(c)
            findings.append(f)
        else:
            checks.append(
                ValidationCheckSummary(
                    check_id=check_id,
                    category=category,
                    label=label,
                    check_state=ValidationCheckState.REQUIRES_REVIEW,
                    truth_state=ValidationTruthState.REQUIRES_REVIEW,
                    context_kind=ValidationContextKind.CASE,
                    finding_count=0,
                    limitations=(f"{label} require doctor review.",),
                )
            )

    # Manufacturing readiness — boundary only unless genuinely supported
    if manufacturing_ready:
        checks.append(
            ValidationCheckSummary(
                check_id="manufacturing_readiness",
                category=ValidationCategory.MANUFACTURING_READINESS,
                label="Manufacturing readiness",
                check_state=ValidationCheckState.REQUIRES_REVIEW,
                truth_state=ValidationTruthState.REQUIRES_REVIEW,
                context_kind=ValidationContextKind.PRODUCTION_EXPORT,
                finding_count=0,
                limitations=("Manufacturing readiness is not clinical approval.",),
            )
        )
    else:
        c, f = _unavailable_check(
            check_id="manufacturing_readiness",
            category=ValidationCategory.MANUFACTURING_READINESS,
            label="Manufacturing readiness",
            reason=(
                "Manufacturing QC / production CAD validation is not available "
                "(boundary-only until WP-10)."
            ),
            context_kind=ValidationContextKind.PRODUCTION_EXPORT,
        )
        checks.append(c)
        findings.append(f)

    # Freshness
    freshness = evaluate_validation_freshness(
        bound_setup_version_id=previous_run.binding.setup_version_id
        if previous_run
        else setup_version_id,
        current_setup_version_id=current_setup_version_id or setup_version_id,
        bound_staging_version_id=previous_run.binding.staging_version_id
        if previous_run
        else staging_version_id,
        current_staging_version_id=current_staging_version_id or staging_version_id,
        bound_clinical_tools_setup_version_id=(
            previous_run.binding.clinical_tools_setup_version_id
            if previous_run
            else clinical_tools_setup_version_id
        ),
        current_clinical_tools_setup_version_id=(
            current_clinical_tools_setup_version_id or clinical_tools_setup_version_id
        ),
        bound_clinical_tools_staging_version_id=(
            previous_run.binding.clinical_tools_staging_version_id
            if previous_run
            else clinical_tools_staging_version_id
        ),
        current_clinical_tools_staging_version_id=(
            current_clinical_tools_staging_version_id or clinical_tools_staging_version_id
        ),
        bound_report_id=previous_run.binding.geometric_report_id if previous_run else (
            validation.report_id if validation else None
        ),
        current_report_id=validation.report_id if validation else None,
        has_run=True,
    )
    if previous_run is None:
        freshness = ValidationFreshness.CURRENT

    # Overall rollup — never claim clinical approval; unavailable does not become PASS
    overall = ValidationCheckState.PASS
    if any(c.check_state is ValidationCheckState.ERROR for c in checks):
        overall = ValidationCheckState.ERROR
    elif any(c.check_state is ValidationCheckState.INVALID for c in checks):
        overall = ValidationCheckState.INVALID
    elif any(c.check_state is ValidationCheckState.WARNING for c in checks):
        overall = ValidationCheckState.WARNING
    elif any(c.check_state is ValidationCheckState.REQUIRES_REVIEW for c in checks):
        overall = ValidationCheckState.REQUIRES_REVIEW
    elif any(c.check_state is ValidationCheckState.NOT_AVAILABLE for c in checks):
        # Mixed PASS + NOT_AVAILABLE → requires review (do not collapse to PASS)
        if any(c.check_state is ValidationCheckState.PASS for c in checks):
            overall = ValidationCheckState.REQUIRES_REVIEW
        else:
            overall = ValidationCheckState.NOT_AVAILABLE

    if freshness is ValidationFreshness.STALE:
        overall_truth = ValidationTruthState.REQUIRES_REVIEW
    elif overall is ValidationCheckState.NOT_AVAILABLE:
        overall_truth = ValidationTruthState.NOT_AVAILABLE
    elif overall is ValidationCheckState.PASS:
        overall_truth = ValidationTruthState.COMPUTED
    else:
        overall_truth = ValidationTruthState.REQUIRES_REVIEW

    passed = sum(1 for c in checks if c.check_state is ValidationCheckState.PASS)
    warnings = sum(1 for c in checks if c.check_state is ValidationCheckState.WARNING)
    errors = sum(
        1
        for c in checks
        if c.check_state in (ValidationCheckState.ERROR, ValidationCheckState.INVALID)
    )
    unavailable = sum(
        1 for c in checks if c.check_state is ValidationCheckState.NOT_AVAILABLE
    )
    review_required = sum(
        1 for c in checks if c.check_state is ValidationCheckState.REQUIRES_REVIEW
    )
    affected_teeth = tuple(
        dict.fromkeys(
            tooth
            for finding in findings
            for tooth in finding.affected_tooth_refs
        )
    )
    affected_stages = tuple(
        sorted(
            {
                finding.stage_index
                for finding in findings
                if finding.stage_index is not None
            }
        )
    )

    binding = ValidationBinding(
        case_id=case_id,
        setup_version_id=setup_version_id,
        staging_version_id=staging_version_id,
        clinical_tools_setup_version_id=clinical_tools_setup_version_id,
        clinical_tools_staging_version_id=clinical_tools_staging_version_id,
        occlusion_registration_version_id=occlusion_registration_version_id,
        geometric_report_id=validation.report_id if validation else None,
        input_hash=input_hash,
        upper_mesh_hash=upper_mesh_hash,
        lower_mesh_hash=lower_mesh_hash,
        config_hash=_config_hash(configuration),
    )

    total_ms = (perf_counter() - started) * 1000
    return ValidationRun(
        validation_run_id=_run_id(
            case_id=case_id,
            report_id=validation.report_id if validation else None,
            setup_version_id=setup_version_id,
            staging_version_id=staging_version_id,
        ),
        contract_version=VALIDATION_CONTRACT_VERSION,
        case_id=case_id,
        binding=binding,
        freshness=freshness,
        overall_check_state=overall,
        overall_truth_state=overall_truth,
        context_kinds=(
            ValidationContextKind.CASE,
            ValidationContextKind.SOURCE,
            ValidationContextKind.TARGET,
            ValidationContextKind.STAGE,
            ValidationContextKind.CLINICAL_TOOLS,
            ValidationContextKind.PRODUCTION_EXPORT,
        ),
        checks=tuple(checks),
        findings=tuple(findings),
        summary=ValidationRunSummary(
            check_count=len(checks),
            checks_passed=passed,
            warnings=warnings,
            errors=errors,
            unavailable_checks=unavailable,
            review_required_checks=review_required,
            finding_count=len(findings),
            affected_teeth=affected_teeth,
            affected_stages=affected_stages,
        ),
        thresholds=tuple(thresholds),
        algorithm=VALIDATION_ALGORITHM_ID,
        algorithm_version=VALIDATION_ALGORITHM_VERSION,
        geometric_engine_version=engine_version,
        generated_at=generated_at,
        provenance=proposal.provenance.value if proposal.provenance else "experimental",
        fixture=bool(proposal.fixture),
        limitations=(
            "GeometricValidationEngine remains the sole geometric authority.",
            "PASS means a supported technical check found no finding under its rules.",
            "PASS is never clinical approval or clinical safety.",
            "Unavailable checks remain NOT_AVAILABLE and are never treated as PASS.",
            "Cross-arch occlusion checks are not invented from dual-arch presence.",
            "WP-10 and later packages are not started.",
        ),
        timings_ms={"validation_2_ms": total_ms},
        legacy_review_summary=legacy if isinstance(legacy, dict) else None,
    )


__all__ = ["build_validation_run"]
