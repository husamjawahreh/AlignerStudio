"""Review-only IPR and attachment proposal models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.case.provenance import DataProvenance
from domain.tooth.identification import Vector3


class ProposalStatus(str, Enum):
    GENERATED = "generated"
    DOCTOR_MODIFIED = "doctor_modified"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    UNABLE_TO_DETERMINE = "unable_to_determine"


@dataclass(frozen=True)
class ProposalWarning:
    code: str
    message: str
    severity: str = "warning"


@dataclass(frozen=True)
class IPRMeasurement:
    value: float | None
    unit: str
    method: str
    status: ProposalStatus


@dataclass(frozen=True)
class IPRSite:
    site_id: str
    tooth_a: int | str
    tooth_b: int | str
    current_measurement: IPRMeasurement
    target_measurement: IPRMeasurement
    required_space: float | None
    proposed_amount: float | None
    confidence: float
    status: ProposalStatus
    warnings: tuple[ProposalWarning, ...]
    provenance: DataProvenance
    fixture: bool
    stage_index: int | None = None


@dataclass(frozen=True)
class IPRProposal:
    proposal_id: str
    plan_id: str
    version_id: str
    sites: tuple[IPRSite, ...]
    status: ProposalStatus
    warnings: tuple[ProposalWarning, ...]
    provenance: DataProvenance
    fixture: bool
    history: tuple[str, ...] = ()


class AttachmentType(str, Enum):
    RECTANGULAR = "rectangular"
    ELLIPTICAL = "elliptical"
    BEVELED = "beveled"
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class AttachmentSite:
    site_id: str
    tooth_number: int | str
    attachment_type: AttachmentType
    reference_point: Vector3 | None
    orientation: tuple[Vector3, Vector3, Vector3] | None
    dimensions: tuple[float, float, float] | None
    reason: str
    confidence: float
    status: ProposalStatus
    warnings: tuple[ProposalWarning, ...]
    provenance: DataProvenance
    fixture: bool
    stage_index: int | None = None
    generated: bool = False


@dataclass(frozen=True)
class AttachmentProposal:
    proposal_id: str
    plan_id: str
    version_id: str
    sites: tuple[AttachmentSite, ...]
    status: ProposalStatus
    warnings: tuple[ProposalWarning, ...]
    provenance: DataProvenance
    fixture: bool
    history: tuple[str, ...] = ()


@dataclass(frozen=True)
class TreatmentProposalResult:
    """All adjunct proposals associated with one immutable plan version."""

    proposal_id: str
    plan_id: str
    version_id: str
    ipr: IPRProposal
    attachments: AttachmentProposal
    provenance: DataProvenance
    fixture: bool
    warnings: tuple[ProposalWarning, ...]
    history: tuple[str, ...] = ()
