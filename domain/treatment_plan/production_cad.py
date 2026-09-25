"""WP-10 Production CAD contracts — manufacturing preparation honesty layer.

Never fabricates shells, trimlines, thickness, undercut, or manufacturing certification.
Never promotes CAD generation to clinical or manufacturing approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


PRODUCTION_CONTRACT_VERSION = "production_cad_1.0"
PRODUCTION_ALGORITHM_ID = "production_cad_honesty_layer"
PRODUCTION_ALGORITHM_VERSION = "production_cad_v1"


class ProductionTruthState(StrEnum):
    VERIFIED = "verified"
    COMPUTED = "computed"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"


class ProductionFreshness(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class ProductionCapabilityState(StrEnum):
    AVAILABLE = "available"
    BOUNDARY_ONLY = "boundary_only"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"
    UNAVAILABLE = "unavailable"


class ProductionSourceKind(StrEnum):
    SELECTED_STAGE = "selected_stage"
    FINAL_TARGET = "final_target"
    EXPLICIT_TREATMENT_STATE = "explicit_treatment_state"
    UNSELECTED = "unselected"


class ProductionQcSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ProductionQcStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    ERROR = "error"
    NOT_AVAILABLE = "not_available"
    REQUIRES_REVIEW = "requires_review"


@dataclass(frozen=True)
class ProductionParameter:
    name: str
    value: float | str | int | bool | None
    unit: str | None
    source: str
    configuration_version: str
    kind: str  # "technical" | "clinical" | "manufacturing"
    provenance: str
    limitations: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "configuration_version": self.configuration_version,
            "kind": self.kind,
            "provenance": self.provenance,
            "limitations": list(self.limitations),
            "clinical_recommendation": False,
            "manufacturing_certified": False,
        }


@dataclass(frozen=True)
class ProductionQcCheck:
    check_id: str
    label: str
    status: ProductionQcStatus
    severity: ProductionQcSeverity
    truth_state: ProductionTruthState
    message: str
    affected_geometry: tuple[str, ...]
    algorithm: str
    algorithm_version: str
    provenance: str
    limitations: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "label": self.label,
            "status": self.status.value,
            "severity": self.severity.value,
            "truth_state": self.truth_state.value,
            "message": self.message,
            "affected_geometry": list(self.affected_geometry),
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "provenance": self.provenance,
            "limitations": list(self.limitations),
            "manufacturing_certified": False,
            "clinically_approved": False,
        }


@dataclass(frozen=True)
class ProductionCapabilityReadiness:
    source_treatment_state: ProductionCapabilityState
    validation_current: ProductionCapabilityState
    shell: ProductionCapabilityState
    trimline: ProductionCapabilityState
    thickness_defined: ProductionCapabilityState
    undercut_analysis: ProductionCapabilityState
    mesh_qc: ProductionCapabilityState
    export_validation: ProductionCapabilityState
    package_integrity: ProductionCapabilityState
    stage_model_export: ProductionCapabilityState
    printable_model_preparation: ProductionCapabilityState
    notes: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "source_treatment_state": self.source_treatment_state.value,
            "validation_current": self.validation_current.value,
            "shell": self.shell.value,
            "trimline": self.trimline.value,
            "thickness_defined": self.thickness_defined.value,
            "undercut_analysis": self.undercut_analysis.value,
            "mesh_qc": self.mesh_qc.value,
            "export_validation": self.export_validation.value,
            "package_integrity": self.package_integrity.value,
            "stage_model_export": self.stage_model_export.value,
            "printable_model_preparation": self.printable_model_preparation.value,
            "notes": list(self.notes),
            "manufacturing_ready": False,
            "manufacturing_certified": False,
            "clinically_approved": False,
        }


@dataclass(frozen=True)
class ProductionBinding:
    case_id: str
    treatment_setup_version_id: str | None
    staging_version_id: str | None
    clinical_tools_setup_version_id: str | None
    clinical_tools_staging_version_id: str | None
    validation_run_id: str | None
    geometric_report_id: str | None
    selected_stage_id: str | None
    selected_stage_index: int | None
    source_kind: ProductionSourceKind
    upper_mesh_hash: str | None
    lower_mesh_hash: str | None
    input_hash: str | None

    def payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "treatment_setup_version_id": self.treatment_setup_version_id,
            "staging_version_id": self.staging_version_id,
            "clinical_tools_setup_version_id": self.clinical_tools_setup_version_id,
            "clinical_tools_staging_version_id": self.clinical_tools_staging_version_id,
            "validation_run_id": self.validation_run_id,
            "geometric_report_id": self.geometric_report_id,
            "selected_stage_id": self.selected_stage_id,
            "selected_stage_index": self.selected_stage_index,
            "source_kind": self.source_kind.value,
            "upper_mesh_hash": self.upper_mesh_hash,
            "lower_mesh_hash": self.lower_mesh_hash,
            "input_hash": self.input_hash,
        }


@dataclass(frozen=True)
class ProductionPlan:
    """Persisted Production CAD boundary document."""

    production_plan_id: str
    production_version_id: str
    parent_production_version_id: str | None
    contract_version: str
    case_id: str
    binding: ProductionBinding
    freshness: ProductionFreshness
    overall_truth_state: ProductionTruthState
    readiness: ProductionCapabilityReadiness
    parameters: tuple[ProductionParameter, ...]
    qc_checks: tuple[ProductionQcCheck, ...]
    operations: tuple[str, ...]
    manufacturing_boundary: dict[str, Any] | None
    export_state: str
    algorithm: str
    algorithm_version: str
    generated_at: str
    provenance: str
    fixture: bool
    limitations: tuple[str, ...]
    timings_ms: dict[str, float | None] = field(default_factory=dict)
    derived_geometry_hashes: dict[str, str] = field(default_factory=dict)
    source_geometry_hashes: dict[str, str | None] = field(default_factory=dict)
    geometry_backends: tuple[dict[str, Any], ...] = ()
    geometry_operations: tuple[dict[str, Any], ...] = ()
    shell_generated: bool = False
    engineering_offset_distance: float | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "production_plan_id": self.production_plan_id,
            "production_version_id": self.production_version_id,
            "parent_production_version_id": self.parent_production_version_id,
            "case_id": self.case_id,
            "binding": self.binding.payload(),
            "freshness": self.freshness.value,
            "overall_truth_state": self.overall_truth_state.value,
            "readiness": self.readiness.payload(),
            "parameters": [item.payload() for item in self.parameters],
            "qc_checks": [item.payload() for item in self.qc_checks],
            "operations": list(self.operations),
            "manufacturing_boundary": self.manufacturing_boundary,
            "export_state": self.export_state,
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "generated_at": self.generated_at,
            "provenance": self.provenance,
            "fixture": self.fixture,
            "limitations": list(self.limitations),
            "timings_ms": dict(self.timings_ms),
            "derived_geometry_hashes": dict(self.derived_geometry_hashes),
            "source_geometry_hashes": dict(self.source_geometry_hashes),
            "geometry_backends": list(self.geometry_backends),
            "geometry_operations": list(self.geometry_operations),
            "engineering_offset_distance": self.engineering_offset_distance,
            "clinically_approved": False,
            "manufacturing_certified": False,
            "manufacturing_ready": False,
            "shell_generated": self.shell_generated,
            "trimline_generated": False,
            "undercut_computed": False,
            "fake_export": False,
        }


def evaluate_production_freshness(
    *,
    bound_setup_version_id: str | None,
    current_setup_version_id: str | None,
    bound_staging_version_id: str | None,
    current_staging_version_id: str | None,
    bound_clinical_tools_setup_version_id: str | None = None,
    current_clinical_tools_setup_version_id: str | None = None,
    bound_validation_run_id: str | None = None,
    current_validation_run_id: str | None = None,
    has_plan: bool,
) -> ProductionFreshness:
    if not has_plan:
        return ProductionFreshness.UNAVAILABLE
    pairs = (
        (bound_setup_version_id, current_setup_version_id),
        (bound_staging_version_id, current_staging_version_id),
        (bound_clinical_tools_setup_version_id, current_clinical_tools_setup_version_id),
        (bound_validation_run_id, current_validation_run_id),
    )
    for bound, current in pairs:
        if bound and current and bound != current:
            return ProductionFreshness.STALE
    return ProductionFreshness.CURRENT


__all__ = [
    "PRODUCTION_ALGORITHM_ID",
    "PRODUCTION_ALGORITHM_VERSION",
    "PRODUCTION_CONTRACT_VERSION",
    "ProductionBinding",
    "ProductionCapabilityReadiness",
    "ProductionCapabilityState",
    "ProductionFreshness",
    "ProductionParameter",
    "ProductionPlan",
    "ProductionQcCheck",
    "ProductionQcSeverity",
    "ProductionQcStatus",
    "ProductionSourceKind",
    "ProductionTruthState",
    "evaluate_production_freshness",
]
