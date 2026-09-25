"""Occlusion representation — honest availability, never invented contacts.

WP-08 expands the capability contract: registration evidence, geometric contact
candidates, provenance, and staleness. Dual-arch crown STLs alone never establish
occlusion. Geometric proximity is never labeled as a clinical occlusal diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any

from domain.case.provenance import DataProvenance


OCCLUSION_CONTRACT_VERSION = "occlusion_1.0"
REGISTRATION_ALGORITHM_ID = "arch_registration_gate"
OCCLUSION_ALGORITHM_ID = "interarch_geometric_proximity"
OCCLUSION_ALGORITHM_VERSION = "occlusion_geom_v1"


class OcclusionAvailability(str, Enum):
    """Legacy availability vocabulary retained for P3 / WP-02 payloads."""

    UNAVAILABLE = "unavailable"
    REQUIRES_REVIEW = "requires_review"
    COMPUTED = "computed"


class OcclusionCapabilityState(StrEnum):
    """WP-08 occlusion capability vocabulary — not a clinical approval flag."""

    UNAVAILABLE = "unavailable"
    SOURCE_REGISTERED = "source_registered"
    COMPUTED = "computed"
    REQUIRES_REVIEW = "requires_review"
    VERIFIED = "verified"


class OcclusionFreshness(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class RegistrationEvidenceKind(StrEnum):
    NONE = "none"
    EXPLICIT_TRANSFORM = "explicit_transform"
    BITE_SCAN = "bite_scan"
    COMMON_COORDINATE_FRAME = "common_coordinate_frame"
    SOURCE_METADATA = "source_metadata"


class ContactSemantics(StrEnum):
    """Precise terminology — geometric findings are never clinical diagnoses."""

    GEOMETRIC_PROXIMITY = "geometric_proximity"
    GEOMETRIC_CONTACT = "geometric_contact"
    CANDIDATE_CONTACT = "candidate_contact"
    CLINICAL_OCCLUSAL_CONTACT = "clinical_occlusal_contact"  # reserved; never assigned without validated method


@dataclass(frozen=True)
class OcclusionRepresentation:
    """Upper/lower registration and bite relationship when source data supports it.

    Dual-arch STL crowns alone do not establish occlusion, bite records, or
    occlusal contacts. Those fields stay UNAVAILABLE until genuine registration
    or bite evidence is present.
    """

    availability: OcclusionAvailability
    upper_lower_registration: OcclusionAvailability
    occlusal_relationship: OcclusionAvailability
    bite_record: OcclusionAvailability
    occlusal_contacts: OcclusionAvailability
    contact_count: int | None
    notes: tuple[str, ...]
    provenance: DataProvenance
    fixture: bool = False

    def payload(self) -> dict:
        return {
            "availability": self.availability.value,
            "upper_lower_registration": self.upper_lower_registration.value,
            "occlusal_relationship": self.occlusal_relationship.value,
            "bite_record": self.bite_record.value,
            "occlusal_contacts": self.occlusal_contacts.value,
            "contact_count": self.contact_count,
            "notes": list(self.notes),
            "provenance": self.provenance.value,
            "fixture": self.fixture,
        }


def unavailable_occlusion(
    *,
    provenance: DataProvenance = DataProvenance.EXPERIMENTAL,
    fixture: bool = False,
    reason: str = (
        "Occlusal registration, bite record, and occlusal contacts are not "
        "provided by crown-only STL analysis."
    ),
) -> OcclusionRepresentation:
    """Honest occlusion stub — does not invent contacts from crown meshes."""
    return OcclusionRepresentation(
        availability=OcclusionAvailability.UNAVAILABLE,
        upper_lower_registration=OcclusionAvailability.UNAVAILABLE,
        occlusal_relationship=OcclusionAvailability.UNAVAILABLE,
        bite_record=OcclusionAvailability.UNAVAILABLE,
        occlusal_contacts=OcclusionAvailability.UNAVAILABLE,
        contact_count=None,
        notes=(reason,),
        provenance=provenance,
        fixture=fixture,
    )


@dataclass(frozen=True)
class RegistrationEvidence:
    """Genuine registration evidence only — never inferred from visual alignment."""

    evidence_kind: RegistrationEvidenceKind
    truth_state: OcclusionCapabilityState
    upper_source_artifact: str | None
    lower_source_artifact: str | None
    upper_source_hash: str | None
    lower_source_hash: str | None
    transform_4x4: tuple[tuple[float, ...], ...] | None
    transform_applies_to: str | None  # "lower_into_upper" | "upper_into_lower" | None
    method: str | None
    method_version: str | None
    quality_metric: float | None
    quality_metric_kind: str | None
    quality_established: bool
    registration_version_id: str | None
    generated_at: str | None
    provenance: DataProvenance
    fixture: bool
    limitations: tuple[str, ...]
    notes: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "evidence_kind": self.evidence_kind.value,
            "truth_state": self.truth_state.value,
            "upper_source_artifact": self.upper_source_artifact,
            "lower_source_artifact": self.lower_source_artifact,
            "upper_source_hash": self.upper_source_hash,
            "lower_source_hash": self.lower_source_hash,
            "transform_4x4": [list(row) for row in self.transform_4x4] if self.transform_4x4 else None,
            "transform_applies_to": self.transform_applies_to,
            "method": self.method,
            "method_version": self.method_version,
            "quality_metric": self.quality_metric,
            "quality_metric_kind": self.quality_metric_kind,
            "quality_established": self.quality_established,
            "registration_version_id": self.registration_version_id,
            "generated_at": self.generated_at,
            "provenance": self.provenance.value,
            "fixture": self.fixture,
            "limitations": list(self.limitations),
            "notes": list(self.notes),
        }


def no_registration_evidence(
    *,
    provenance: DataProvenance,
    fixture: bool,
    upper_source_artifact: str | None = None,
    lower_source_artifact: str | None = None,
    upper_source_hash: str | None = None,
    lower_source_hash: str | None = None,
    generated_at: str | None = None,
    reason: str = (
        "No genuine bite registration, validated transform, or common-frame "
        "metadata is present. Independent upper/lower scans do not establish occlusion."
    ),
) -> RegistrationEvidence:
    return RegistrationEvidence(
        evidence_kind=RegistrationEvidenceKind.NONE,
        truth_state=OcclusionCapabilityState.UNAVAILABLE,
        upper_source_artifact=upper_source_artifact,
        lower_source_artifact=lower_source_artifact,
        upper_source_hash=upper_source_hash,
        lower_source_hash=lower_source_hash,
        transform_4x4=None,
        transform_applies_to=None,
        method=None,
        method_version=None,
        quality_metric=None,
        quality_metric_kind=None,
        quality_established=False,
        registration_version_id=None,
        generated_at=generated_at,
        provenance=provenance,
        fixture=fixture,
        limitations=(reason,),
        notes=(reason,),
    )


@dataclass(frozen=True)
class GeometricContactCandidate:
    """Inter-arch geometric proximity/contact candidate — not a clinical diagnosis."""

    candidate_id: str
    upper_tooth_ref: str | None
    lower_tooth_ref: str | None
    upper_instance_id: int | None
    lower_instance_id: int | None
    distance: float | None
    unit: str
    semantics: ContactSemantics
    method: str
    method_version: str
    technical_threshold: float | None
    technical_threshold_kind: str | None
    truth_state: OcclusionCapabilityState
    clinical_interpretation: None  # always None — geometric only
    limitations: tuple[str, ...]
    provenance: DataProvenance
    fixture: bool

    def payload(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "upper_tooth_ref": self.upper_tooth_ref,
            "lower_tooth_ref": self.lower_tooth_ref,
            "upper_instance_id": self.upper_instance_id,
            "lower_instance_id": self.lower_instance_id,
            "distance": self.distance,
            "unit": self.unit,
            "semantics": self.semantics.value,
            "method": self.method,
            "method_version": self.method_version,
            "technical_threshold": self.technical_threshold,
            "technical_threshold_kind": self.technical_threshold_kind,
            "truth_state": self.truth_state.value,
            "clinical_interpretation": self.clinical_interpretation,
            "clinical_diagnosis": None,
            "limitations": list(self.limitations),
            "provenance": self.provenance.value,
            "fixture": self.fixture,
        }


@dataclass(frozen=True)
class ArchRelationshipDescriptor:
    """Arch relationship — clinical Class/OJ/OB diagnoses stay unavailable without validated methods."""

    truth_state: OcclusionCapabilityState
    class_i_ii_iii: OcclusionCapabilityState
    overjet: OcclusionCapabilityState
    overbite: OcclusionCapabilityState
    crossbite: OcclusionCapabilityState
    open_bite: OcclusionCapabilityState
    deep_bite: OcclusionCapabilityState
    geometric_notes: tuple[str, ...]
    limitations: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "truth_state": self.truth_state.value,
            "class_i_ii_iii": self.class_i_ii_iii.value,
            "overjet": self.overjet.value,
            "overbite": self.overbite.value,
            "crossbite": self.crossbite.value,
            "open_bite": self.open_bite.value,
            "deep_bite": self.deep_bite.value,
            "geometric_notes": list(self.geometric_notes),
            "limitations": list(self.limitations),
            "clinical_diagnosis": None,
        }


def unavailable_arch_relationship(
    reason: str = (
        "Class I/II/III, overjet, overbite, crossbite, open bite, and deep bite "
        "are not inferred from geometry heuristics."
    ),
) -> ArchRelationshipDescriptor:
    na = OcclusionCapabilityState.UNAVAILABLE
    return ArchRelationshipDescriptor(
        truth_state=na,
        class_i_ii_iii=na,
        overjet=na,
        overbite=na,
        crossbite=na,
        open_bite=na,
        deep_bite=na,
        geometric_notes=(),
        limitations=(reason,),
    )


@dataclass(frozen=True)
class OcclusionCapabilityReadiness:
    """Per-capability gates — not a single occlusion boolean."""

    registration: OcclusionCapabilityState
    occlusion: OcclusionCapabilityState
    geometric_contacts: OcclusionCapabilityState
    arch_relationship: OcclusionCapabilityState
    doctor_review_required: bool
    clinically_approved: bool = False
    notes: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "registration": self.registration.value,
            "occlusion": self.occlusion.value,
            "geometric_contacts": self.geometric_contacts.value,
            "arch_relationship": self.arch_relationship.value,
            "doctor_review_required": self.doctor_review_required,
            "clinically_approved": False,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class OcclusionResult:
    """Full WP-08 occlusion capability document."""

    contract_version: str
    case_id: str
    capability_state: OcclusionCapabilityState
    representation: OcclusionRepresentation
    registration: RegistrationEvidence
    contact_candidates: tuple[GeometricContactCandidate, ...]
    arch_relationship: ArchRelationshipDescriptor
    readiness: OcclusionCapabilityReadiness
    freshness: OcclusionFreshness
    bound_source_input_hash: str | None
    bound_upper_hash: str | None
    bound_lower_hash: str | None
    bound_registration_version_id: str | None
    bound_setup_version_id: str | None
    bound_staging_version_id: str | None
    generated_at: str
    algorithm: str | None
    algorithm_version: str | None
    provenance: DataProvenance
    fixture: bool
    limitations: tuple[str, ...]
    timings_ms: dict[str, float | None] = field(default_factory=dict)
    technical_threshold: float | None = None
    technical_threshold_kind: str | None = None
    technical_threshold_version: str | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "case_id": self.case_id,
            "capability_state": self.capability_state.value,
            "representation": self.representation.payload(),
            "registration": self.registration.payload(),
            "contact_candidates": [item.payload() for item in self.contact_candidates],
            "arch_relationship": self.arch_relationship.payload(),
            "readiness": self.readiness.payload(),
            "freshness": self.freshness.value,
            "bound_source_input_hash": self.bound_source_input_hash,
            "bound_upper_hash": self.bound_upper_hash,
            "bound_lower_hash": self.bound_lower_hash,
            "bound_registration_version_id": self.bound_registration_version_id,
            "bound_setup_version_id": self.bound_setup_version_id,
            "bound_staging_version_id": self.bound_staging_version_id,
            "generated_at": self.generated_at,
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "provenance": self.provenance.value,
            "fixture": self.fixture,
            "limitations": list(self.limitations),
            "timings_ms": dict(self.timings_ms),
            "technical_threshold": self.technical_threshold,
            "technical_threshold_kind": self.technical_threshold_kind,
            "technical_threshold_version": self.technical_threshold_version,
            "clinically_approved": False,
            "occlusion_validated": False,
        }


def evaluate_occlusion_freshness(
    *,
    bound_upper_hash: str | None,
    bound_lower_hash: str | None,
    current_upper_hash: str | None,
    current_lower_hash: str | None,
    bound_registration_version_id: str | None,
    current_registration_version_id: str | None,
    bound_setup_version_id: str | None = None,
    current_setup_version_id: str | None = None,
    bound_staging_version_id: str | None = None,
    current_staging_version_id: str | None = None,
    has_result: bool,
) -> OcclusionFreshness:
    """Mark occlusion stale when source, registration, setup, or staging versions diverge."""
    if not has_result:
        return OcclusionFreshness.UNAVAILABLE
    if bound_upper_hash and current_upper_hash and bound_upper_hash != current_upper_hash:
        return OcclusionFreshness.STALE
    if bound_lower_hash and current_lower_hash and bound_lower_hash != current_lower_hash:
        return OcclusionFreshness.STALE
    if (
        bound_registration_version_id
        and current_registration_version_id
        and bound_registration_version_id != current_registration_version_id
    ):
        return OcclusionFreshness.STALE
    if (
        bound_setup_version_id
        and current_setup_version_id
        and bound_setup_version_id != current_setup_version_id
    ):
        return OcclusionFreshness.STALE
    if (
        bound_staging_version_id
        and current_staging_version_id
        and bound_staging_version_id != current_staging_version_id
    ):
        return OcclusionFreshness.STALE
    return OcclusionFreshness.CURRENT


__all__ = [
    "OCCLUSION_ALGORITHM_ID",
    "OCCLUSION_ALGORITHM_VERSION",
    "OCCLUSION_CONTRACT_VERSION",
    "REGISTRATION_ALGORITHM_ID",
    "ArchRelationshipDescriptor",
    "ContactSemantics",
    "GeometricContactCandidate",
    "OcclusionAvailability",
    "OcclusionCapabilityReadiness",
    "OcclusionCapabilityState",
    "OcclusionFreshness",
    "OcclusionRepresentation",
    "OcclusionResult",
    "RegistrationEvidence",
    "RegistrationEvidenceKind",
    "evaluate_occlusion_freshness",
    "no_registration_evidence",
    "unavailable_arch_relationship",
    "unavailable_occlusion",
]
