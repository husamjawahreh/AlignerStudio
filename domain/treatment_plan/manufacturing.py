"""Manufacturing / appliance boundary — architecture only, no fake geometry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ArtifactLayer(str, Enum):
    """Clear separation between treatment and manufacturing concerns."""

    TREATMENT_DESIGN = "treatment_design"
    GEOMETRIC_VALIDATION = "geometric_validation"
    MANUFACTURING_PREPARATION = "manufacturing_preparation"
    MANUFACTURING_VALIDATION = "manufacturing_validation"


class ManufacturingCapabilityStatus(str, Enum):
    """Honest capability state for manufacturing features."""

    UNAVAILABLE = "unavailable"
    BOUNDARY_ONLY = "boundary_only"
    COMPUTED = "computed"


@dataclass(frozen=True)
class ManufacturingBoundaryReport:
    """P5 manufacturing boundary: what exists vs what must not be invented."""

    package_kind: str
    stage_model_export: ManufacturingCapabilityStatus
    appliance_shell_generation: ManufacturingCapabilityStatus
    trimline_cutline: ManufacturingCapabilityStatus
    shell_thickness_material_profile: ManufacturingCapabilityStatus
    undercut_engagement_checks: ManufacturingCapabilityStatus
    printable_model_preparation: ManufacturingCapabilityStatus
    manufacturing_qc_report: ManufacturingCapabilityStatus
    treatment_vs_manufacturing_separated: bool
    notes: tuple[str, ...]

    def payload(self) -> dict[str, object]:
        return {
            "packageKind": self.package_kind,
            "artifactLayers": [layer.value for layer in ArtifactLayer],
            "stageModelExport": self.stage_model_export.value,
            "applianceShellGeneration": self.appliance_shell_generation.value,
            "trimlineCutline": self.trimline_cutline.value,
            "shellThicknessMaterialProfile": self.shell_thickness_material_profile.value,
            "undercutEngagementChecks": self.undercut_engagement_checks.value,
            "printableModelPreparation": self.printable_model_preparation.value,
            "manufacturingQcReport": self.manufacturing_qc_report.value,
            "treatmentVsManufacturingSeparated": self.treatment_vs_manufacturing_separated,
            "notes": list(self.notes),
        }


def build_manufacturing_boundary_report(*, has_stage_models: bool) -> ManufacturingBoundaryReport:
    """Stage STL export is treatment-stage geometry, not appliance shells."""
    notes = [
        "Stage model export contains treatment-stage meshes for review/audit only.",
        "Appliance shell generation is unavailable; no fake shells are produced.",
        "Trimline/cutline, shell thickness, undercut, and manufacturing QC are unavailable.",
        "Treatment design and geometric validation are separated from manufacturing preparation.",
    ]
    return ManufacturingBoundaryReport(
        package_kind="engineering_treatment_export",
        stage_model_export=(
            ManufacturingCapabilityStatus.COMPUTED
            if has_stage_models
            else ManufacturingCapabilityStatus.UNAVAILABLE
        ),
        appliance_shell_generation=ManufacturingCapabilityStatus.UNAVAILABLE,
        trimline_cutline=ManufacturingCapabilityStatus.UNAVAILABLE,
        shell_thickness_material_profile=ManufacturingCapabilityStatus.UNAVAILABLE,
        undercut_engagement_checks=ManufacturingCapabilityStatus.UNAVAILABLE,
        printable_model_preparation=(
            ManufacturingCapabilityStatus.BOUNDARY_ONLY
            if has_stage_models
            else ManufacturingCapabilityStatus.UNAVAILABLE
        ),
        manufacturing_qc_report=ManufacturingCapabilityStatus.UNAVAILABLE,
        treatment_vs_manufacturing_separated=True,
        notes=tuple(notes),
    )
