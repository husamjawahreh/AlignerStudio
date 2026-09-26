"""FV-02 source-artifact contract.

The source file is immutable. Arch, units, FDI, and occlusion are recorded
only when the caller actually supplied them. Filename text is not an arch.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class IntakeReadiness(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED_INVALID_INPUT = "BLOCKED_INVALID_INPUT"


class ArchAssignment(StrEnum):
    UPPER = "upper"
    LOWER = "lower"
    ARCH_UNKNOWN = "ARCH_UNKNOWN"


class OrientationKind(StrEnum):
    SOURCE_COORDINATES = "SOURCE_COORDINATES"
    NORMALIZED_VIEW_COORDINATES = "NORMALIZED_VIEW_COORDINATES"
    CLINICAL_ORIENTATION = "CLINICAL_ORIENTATION"
    MODEL_ORIENTATION = "MODEL_ORIENTATION"
    COMPUTED_GEOMETRIC_ORIENTATION = "COMPUTED_GEOMETRIC_ORIENTATION"


def resolve_arch(*, explicit: str | None) -> dict[str, Any]:
    """Persist an arch only when the caller supplied upper or lower."""
    normalized = (explicit or "").strip().lower()
    if normalized in {ArchAssignment.UPPER.value, ArchAssignment.LOWER.value}:
        return {
            "arch": normalized,
            "truth": "USER_PROVIDED",
            "method": "explicit_upload_parameter",
            "confidence": None,
            "filename_used": False,
        }
    return {
        "arch": ArchAssignment.ARCH_UNKNOWN.value,
        "truth": ArchAssignment.ARCH_UNKNOWN.value,
        "method": None,
        "confidence": None,
        "filename_used": False,
    }


def case_arch_summary(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """One, both, or neither arch. Dual presence is not occlusion."""
    arches = {item.get("arch", {}).get("arch") for item in artifacts}
    return {
        "upper_present": "upper" in arches,
        "lower_present": "lower" in arches,
        "unknown_present": ArchAssignment.ARCH_UNKNOWN.value in arches,
        "arch_count": len([item for item in artifacts if item.get("role") == "SOURCE_FILE"]),
        "requires_both_arches": False,
        "occlusion_established": False,
        "bite_registration_established": False,
        "contact_established": False,
        "jaw_relationship_established": False,
        "fdi_assigned": False,
    }


def readiness_from_findings(*, blockers: list[str], warnings: list[str]) -> str:
    if blockers:
        return IntakeReadiness.BLOCKED_INVALID_INPUT.value
    if warnings:
        return IntakeReadiness.READY_WITH_WARNINGS.value
    return IntakeReadiness.READY.value


_PRIVATE_KEYS = {"original_filename", "patient_reference", "source_path", "output_path"}


def privacy_log_view(record: dict[str, Any]) -> dict[str, Any]:
    """Technical log payload. Drops filename, patient reference, and stored paths."""

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: scrub(item)
                for key, item in value.items()
                if key not in _PRIVATE_KEYS
            }
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    scrubbed = scrub(record)
    return scrubbed if isinstance(scrubbed, dict) else {}


def segmentation_input_binding(
    source_sha256: str, derived_sha256: str | None = None
) -> dict[str, Any]:
    """Segmentation reads the source hash unless a later phase selects a derived mesh."""
    return {
        "role": "SEGMENTATION_INPUT",
        "sha256": source_sha256,
        "source_sha256": source_sha256,
        "derived_sha256": derived_sha256,
        "uses_derived_hash_as_source": False,
    }
