"""WP-09 Validation 2.0 contracts — honesty layer over GeometricValidationEngine.

Never replaces the geometric engine. Never promotes PASS to clinical approval.
Unavailable capability checks remain explicitly unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


VALIDATION_CONTRACT_VERSION = "validation_2.0"
VALIDATION_ALGORITHM_ID = "validation_2_honesty_layer"
VALIDATION_ALGORITHM_VERSION = "validation_2_v1"


class ValidationTruthState(StrEnum):
    VERIFIED = "verified"
    COMPUTED = "computed"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"


class ValidationFreshness(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class ValidationCheckState(StrEnum):
    """Result of one check — PASS is technical only, never clinical approval."""

    PASS = "pass"
    WARNING = "warning"
    ERROR = "error"
    INVALID = "invalid"
    NOT_AVAILABLE = "not_available"
    REQUIRES_REVIEW = "requires_review"


class ValidationSeverity(StrEnum):
    """Technical severity — never mapped automatically to clinical urgency."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationCategory(StrEnum):
    COLLISION = "collision"
    PROXIMITY = "proximity"
    CONTACT = "contact"
    GEOMETRY_DATA_QUALITY = "geometry_data_quality"
    SOURCE_CONSISTENCY = "source_consistency"
    TREATMENT_STATE_CONSISTENCY = "treatment_state_consistency"
    STAGING_CONSISTENCY = "staging_consistency"
    CLINICAL_TOOL_CONSISTENCY = "clinical_tool_consistency"
    OCCLUSION_CAPABILITY = "occlusion_capability"
    MANUFACTURING_READINESS = "manufacturing_readiness"
    MOVEMENT_CONSTRAINTS = "movement_constraints"
    ROOT_ANATOMY = "root_anatomy"
    CLINICAL_AXES = "clinical_axes"
    LANDMARKS = "landmarks"


class ValidationContextKind(StrEnum):
    SOURCE = "source"
    TARGET = "target"
    STAGE = "stage"
    CLINICAL_TOOLS = "clinical_tools"
    PRODUCTION_EXPORT = "production_export"
    CASE = "case"


@dataclass(frozen=True)
class ValidationThresholdRecord:
    """Explicit technical threshold — never a clinical limit unless declared."""

    name: str
    value: float | None
    unit: str
    kind: str  # "technical" | "clinical"
    version: str
    source: str

    def payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "kind": self.kind,
            "version": self.version,
            "source": self.source,
            "clinical_limit": False if self.kind == "technical" else self.kind == "clinical",
        }


@dataclass(frozen=True)
class ValidationFinding:
    finding_id: str
    category: ValidationCategory
    severity: ValidationSeverity
    check_state: ValidationCheckState
    truth_state: ValidationTruthState
    affected_tooth_refs: tuple[str | int, ...]
    arch: str | None
    stage_index: int | None
    context_kind: ValidationContextKind
    measured_value: float | None
    measured_unit: str | None
    threshold: ValidationThresholdRecord | None
    source: str
    algorithm: str
    algorithm_version: str
    message: str
    review_state: str
    provenance: str
    limitations: tuple[str, ...]
    clinical_interpretation: None = None
    spatial_binding: dict[str, Any] | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "check_state": self.check_state.value,
            "truth_state": self.truth_state.value,
            "affected_tooth_refs": list(self.affected_tooth_refs),
            "arch": self.arch,
            "stage_index": self.stage_index,
            "context_kind": self.context_kind.value,
            "measured_value": self.measured_value,
            "measured_unit": self.measured_unit,
            "threshold": self.threshold.payload() if self.threshold else None,
            "source": self.source,
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "message": self.message,
            "review_state": self.review_state,
            "provenance": self.provenance,
            "limitations": list(self.limitations),
            "clinical_interpretation": None,
            "clinical_diagnosis": None,
            "spatial_binding": self.spatial_binding,
        }


@dataclass(frozen=True)
class ValidationCheckSummary:
    """One named check in the Validation 2.0 catalog."""

    check_id: str
    category: ValidationCategory
    label: str
    check_state: ValidationCheckState
    truth_state: ValidationTruthState
    context_kind: ValidationContextKind
    finding_count: int
    limitations: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "category": self.category.value,
            "label": self.label,
            "check_state": self.check_state.value,
            "truth_state": self.truth_state.value,
            "context_kind": self.context_kind.value,
            "finding_count": self.finding_count,
            "limitations": list(self.limitations),
            "clinically_approved": False,
        }


@dataclass(frozen=True)
class ValidationBinding:
    case_id: str
    setup_version_id: str | None
    staging_version_id: str | None
    clinical_tools_setup_version_id: str | None
    clinical_tools_staging_version_id: str | None
    occlusion_registration_version_id: str | None
    geometric_report_id: str | None
    input_hash: str | None
    upper_mesh_hash: str | None
    lower_mesh_hash: str | None
    config_hash: str | None

    def payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "setup_version_id": self.setup_version_id,
            "staging_version_id": self.staging_version_id,
            "clinical_tools_setup_version_id": self.clinical_tools_setup_version_id,
            "clinical_tools_staging_version_id": self.clinical_tools_staging_version_id,
            "occlusion_registration_version_id": self.occlusion_registration_version_id,
            "geometric_report_id": self.geometric_report_id,
            "input_hash": self.input_hash,
            "upper_mesh_hash": self.upper_mesh_hash,
            "lower_mesh_hash": self.lower_mesh_hash,
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True)
class ValidationRunSummary:
    check_count: int
    checks_passed: int
    warnings: int
    errors: int
    unavailable_checks: int
    review_required_checks: int
    finding_count: int
    affected_teeth: tuple[str | int, ...]
    affected_stages: tuple[int, ...]
    clinically_approved: bool = False

    def payload(self) -> dict[str, Any]:
        return {
            "check_count": self.check_count,
            "checks_passed": self.checks_passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "unavailable_checks": self.unavailable_checks,
            "review_required_checks": self.review_required_checks,
            "finding_count": self.finding_count,
            "affected_teeth": list(self.affected_teeth),
            "affected_stages": list(self.affected_stages),
            "clinically_approved": False,
            "clinical_safety_guarantee": False,
            "validation_score": None,
        }


@dataclass(frozen=True)
class ValidationRun:
    """Versioned Validation 2.0 document wrapping GeometricValidationEngine output."""

    validation_run_id: str
    contract_version: str
    case_id: str
    binding: ValidationBinding
    freshness: ValidationFreshness
    overall_check_state: ValidationCheckState
    overall_truth_state: ValidationTruthState
    context_kinds: tuple[ValidationContextKind, ...]
    checks: tuple[ValidationCheckSummary, ...]
    findings: tuple[ValidationFinding, ...]
    summary: ValidationRunSummary
    thresholds: tuple[ValidationThresholdRecord, ...]
    algorithm: str
    algorithm_version: str
    geometric_engine_version: str | None
    generated_at: str
    provenance: str
    fixture: bool
    limitations: tuple[str, ...]
    timings_ms: dict[str, float | None] = field(default_factory=dict)
    legacy_review_summary: dict[str, Any] | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "validation_run_id": self.validation_run_id,
            "case_id": self.case_id,
            "binding": self.binding.payload(),
            "freshness": self.freshness.value,
            "overall_check_state": self.overall_check_state.value,
            "overall_truth_state": self.overall_truth_state.value,
            "context_kinds": [item.value for item in self.context_kinds],
            "checks": [item.payload() for item in self.checks],
            "findings": [item.payload() for item in self.findings],
            "summary": self.summary.payload(),
            "thresholds": [item.payload() for item in self.thresholds],
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "geometric_engine_version": self.geometric_engine_version,
            "generated_at": self.generated_at,
            "provenance": self.provenance,
            "fixture": self.fixture,
            "limitations": list(self.limitations),
            "timings_ms": dict(self.timings_ms),
            "legacy_review_summary": self.legacy_review_summary,
            "clinically_approved": False,
            "clinical_safety_guarantee": False,
            "pass_means_clinical_approval": False,
        }


def evaluate_validation_freshness(
    *,
    bound_setup_version_id: str | None,
    current_setup_version_id: str | None,
    bound_staging_version_id: str | None,
    current_staging_version_id: str | None,
    bound_clinical_tools_setup_version_id: str | None = None,
    current_clinical_tools_setup_version_id: str | None = None,
    bound_clinical_tools_staging_version_id: str | None = None,
    current_clinical_tools_staging_version_id: str | None = None,
    bound_report_id: str | None = None,
    current_report_id: str | None = None,
    has_run: bool,
) -> ValidationFreshness:
    if not has_run:
        return ValidationFreshness.UNAVAILABLE
    pairs = (
        (bound_setup_version_id, current_setup_version_id),
        (bound_staging_version_id, current_staging_version_id),
        (bound_clinical_tools_setup_version_id, current_clinical_tools_setup_version_id),
        (bound_clinical_tools_staging_version_id, current_clinical_tools_staging_version_id),
        (bound_report_id, current_report_id),
    )
    for bound, current in pairs:
        if bound and current and bound != current:
            return ValidationFreshness.STALE
    return ValidationFreshness.CURRENT


__all__ = [
    "VALIDATION_ALGORITHM_ID",
    "VALIDATION_ALGORITHM_VERSION",
    "VALIDATION_CONTRACT_VERSION",
    "ValidationBinding",
    "ValidationCategory",
    "ValidationCheckState",
    "ValidationCheckSummary",
    "ValidationContextKind",
    "ValidationFinding",
    "ValidationFreshness",
    "ValidationRun",
    "ValidationRunSummary",
    "ValidationSeverity",
    "ValidationThresholdRecord",
    "ValidationTruthState",
    "evaluate_validation_freshness",
]
