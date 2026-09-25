"""Dental Intelligence 2.0 domain contracts — truth-preserving clinical intelligence.

WP-02: every field carries an explicit truth state. Never invent FDI, landmarks,
clinical dental axes, or occlusion. Geometry-derived quantities are COMPUTED,
not VERIFIED clinical facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

from domain.case.provenance import DataProvenance

T = TypeVar("T")

INTELLIGENCE_CONTRACT_VERSION = "dental_intelligence_2.0"
GEOMETRY_ALGORITHM_VERSION = "mesh_metrics_v1"


class IntelligenceTruthState(StrEnum):
    """Doctor/system truth vocabulary — never silently promote between states."""

    VERIFIED = "verified"
    COMPUTED = "computed"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"


@dataclass(frozen=True)
class TruthValue(Generic[T]):
    """A value paired with an explicit truth state and optional limitation note."""

    state: IntelligenceTruthState
    value: T | None = None
    reason: str | None = None
    algorithm: str | None = None
    algorithm_version: str | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "value": self.value,
            "reason": self.reason,
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
        }


def not_available(reason: str, *, algorithm: str | None = None) -> TruthValue[Any]:
    return TruthValue(
        state=IntelligenceTruthState.NOT_AVAILABLE,
        value=None,
        reason=reason,
        algorithm=algorithm,
        algorithm_version=None,
    )


def computed(
    value: Any,
    *,
    algorithm: str,
    algorithm_version: str,
    reason: str | None = None,
) -> TruthValue[Any]:
    return TruthValue(
        state=IntelligenceTruthState.COMPUTED,
        value=value,
        reason=reason,
        algorithm=algorithm,
        algorithm_version=algorithm_version,
    )


def requires_review(
    value: Any | None = None,
    *,
    reason: str,
    algorithm: str | None = None,
    algorithm_version: str | None = None,
) -> TruthValue[Any]:
    return TruthValue(
        state=IntelligenceTruthState.REQUIRES_REVIEW,
        value=value,
        reason=reason,
        algorithm=algorithm,
        algorithm_version=algorithm_version,
    )


def verified(
    value: Any,
    *,
    reason: str | None = None,
    algorithm: str | None = None,
    algorithm_version: str | None = None,
) -> TruthValue[Any]:
    return TruthValue(
        state=IntelligenceTruthState.VERIFIED,
        value=value,
        reason=reason,
        algorithm=algorithm,
        algorithm_version=algorithm_version,
    )


@dataclass(frozen=True)
class GeometryMetrics:
    """Deterministic mesh-derived metrics — not clinical dental measurements."""

    vertex_count: int
    face_count: int
    centroid: tuple[float, float, float]
    bounding_box_min: tuple[float, float, float]
    bounding_box_max: tuple[float, float, float]
    extents: tuple[float, float, float]
    surface_area: float | None
    volume: float | None
    principal_directions: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ] | None
    principal_directions_kind: str  # always "mesh_pca" when present — never "clinical_dental_axes"
    mesh_finite: bool
    empty_geometry: bool

    def payload(self) -> dict[str, Any]:
        return {
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "centroid": list(self.centroid),
            "bounding_box_min": list(self.bounding_box_min),
            "bounding_box_max": list(self.bounding_box_max),
            "extents": list(self.extents),
            "surface_area": self.surface_area,
            "volume": self.volume,
            "principal_directions": (
                [list(axis) for axis in self.principal_directions]
                if self.principal_directions
                else None
            ),
            "principal_directions_kind": self.principal_directions_kind,
            "mesh_finite": self.mesh_finite,
            "empty_geometry": self.empty_geometry,
        }


@dataclass(frozen=True)
class ToothIntelligence:
    """Per-tooth intelligence with explicit truth states for each clinical concept."""

    instance_id: int
    tooth_ref: str | None
    arch: str | None
    fdi_number: TruthValue[int]
    semantic_label: TruthValue[int]
    identification_status: str | None
    identification_confidence: float | None  # null when unavailable — never invented
    geometry: TruthValue[dict[str, Any]]
    crown_geometry: TruthValue[bool]
    root_geometry: TruthValue[bool]
    landmarks: TruthValue[dict[str, Any]]
    local_coordinate_frame: TruthValue[dict[str, Any]]
    clinical_dental_axes: TruthValue[dict[str, Any]]
    mesh_principal_directions: TruthValue[list[list[float]]]
    quality_findings: tuple[str, ...]
    overall_truth_state: IntelligenceTruthState
    provenance: DataProvenance
    fixture: bool
    source_mesh_path: str | None = None
    source_mesh_sha256: str | None = None
    model_name: str | None = None
    model_version: str | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "tooth_ref": self.tooth_ref,
            "arch": self.arch,
            "fdi_number": self.fdi_number.payload(),
            "semantic_label": self.semantic_label.payload(),
            "identification_status": self.identification_status,
            "identification_confidence": self.identification_confidence,
            "geometry": self.geometry.payload(),
            "crown_geometry": self.crown_geometry.payload(),
            "root_geometry": self.root_geometry.payload(),
            "landmarks": self.landmarks.payload(),
            "local_coordinate_frame": self.local_coordinate_frame.payload(),
            "clinical_dental_axes": self.clinical_dental_axes.payload(),
            "mesh_principal_directions": self.mesh_principal_directions.payload(),
            "quality_findings": list(self.quality_findings),
            "overall_truth_state": self.overall_truth_state.value,
            "provenance": self.provenance.value,
            "fixture": self.fixture,
            "source_mesh_path": self.source_mesh_path,
            "source_mesh_sha256": self.source_mesh_sha256,
            "model_name": self.model_name,
            "model_version": self.model_version,
        }


@dataclass(frozen=True)
class ArchIntelligence:
    """Arch-level intelligence summary — no clinical conclusions from count alone."""

    arch: str
    tooth_instance_count: int
    resolved_fdi_count: int
    unresolved_identity_count: int
    geometry_ready_count: int
    landmarks_available_count: int
    clinical_axes_available_count: int
    quality_findings: tuple[str, ...]
    overall_truth_state: IntelligenceTruthState
    provenance: DataProvenance
    fixture: bool
    source_mesh_path: str | None = None
    source_mesh_sha256: str | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "arch": self.arch,
            "tooth_instance_count": self.tooth_instance_count,
            "resolved_fdi_count": self.resolved_fdi_count,
            "unresolved_identity_count": self.unresolved_identity_count,
            "geometry_ready_count": self.geometry_ready_count,
            "landmarks_available_count": self.landmarks_available_count,
            "clinical_axes_available_count": self.clinical_axes_available_count,
            "quality_findings": list(self.quality_findings),
            "overall_truth_state": self.overall_truth_state.value,
            "provenance": self.provenance.value,
            "fixture": self.fixture,
            "source_mesh_path": self.source_mesh_path,
            "source_mesh_sha256": self.source_mesh_sha256,
        }


@dataclass(frozen=True)
class CapabilityReadiness:
    """Machine-readable prerequisites for downstream workflows — not clinical scores."""

    identity_readiness: IntelligenceTruthState
    geometry_readiness: IntelligenceTruthState
    axis_readiness: IntelligenceTruthState
    occlusion_readiness: IntelligenceTruthState
    treatment_setup_readiness: IntelligenceTruthState
    validation_readiness: IntelligenceTruthState
    reasons: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "identity_readiness": self.identity_readiness.value,
            "geometry_readiness": self.geometry_readiness.value,
            "axis_readiness": self.axis_readiness.value,
            "occlusion_readiness": self.occlusion_readiness.value,
            "treatment_setup_readiness": self.treatment_setup_readiness.value,
            "validation_readiness": self.validation_readiness.value,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class CaseDentalIntelligence:
    """Case-level Dental Intelligence 2.0 document — versioned, provenance-bound."""

    contract_version: str
    case_id: str
    job_id: str | None
    input_hash: str | None
    processing_mode: str | None
    generated_at: str
    teeth: tuple[ToothIntelligence, ...]
    arches: tuple[ArchIntelligence, ...]
    occlusion: TruthValue[dict[str, Any]]
    data_quality_findings: tuple[str, ...]
    capability_readiness: CapabilityReadiness
    overall_truth_state: IntelligenceTruthState
    provenance: DataProvenance
    fixture: bool
    model_name: str | None = None
    model_version: str | None = None
    timings_ms: dict[str, float | None] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "case_id": self.case_id,
            "job_id": self.job_id,
            "input_hash": self.input_hash,
            "processing_mode": self.processing_mode,
            "generated_at": self.generated_at,
            "teeth": [tooth.payload() for tooth in self.teeth],
            "arches": [arch.payload() for arch in self.arches],
            "occlusion": self.occlusion.payload(),
            "data_quality_findings": list(self.data_quality_findings),
            "capability_readiness": self.capability_readiness.payload(),
            "overall_truth_state": self.overall_truth_state.value,
            "provenance": self.provenance.value,
            "fixture": self.fixture,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "timings_ms": dict(self.timings_ms),
            "limitations": list(self.limitations),
            # Aggregate counts for evidence reporting (derived, not invented clinical facts).
            "counts": {
                "tooth_instances": len(self.teeth),
                "resolved_fdi": sum(
                    1 for tooth in self.teeth if tooth.fdi_number.state is IntelligenceTruthState.VERIFIED
                    or (
                        tooth.fdi_number.state is IntelligenceTruthState.REQUIRES_REVIEW
                        and tooth.fdi_number.value is not None
                    )
                ),
                "unresolved_identity": sum(
                    1
                    for tooth in self.teeth
                    if tooth.fdi_number.state is IntelligenceTruthState.NOT_AVAILABLE
                ),
                "arch_assigned": sum(1 for tooth in self.teeth if tooth.arch),
                "clinical_axes_available": sum(
                    1
                    for tooth in self.teeth
                    if tooth.clinical_dental_axes.state
                    in (IntelligenceTruthState.VERIFIED, IntelligenceTruthState.COMPUTED)
                ),
                "landmarks_available": sum(
                    1
                    for tooth in self.teeth
                    if tooth.landmarks.state
                    in (IntelligenceTruthState.VERIFIED, IntelligenceTruthState.COMPUTED)
                ),
                "occlusion_available": self.occlusion.state
                not in (
                    IntelligenceTruthState.NOT_AVAILABLE,
                    IntelligenceTruthState.REQUIRES_REVIEW,
                )
                and self.occlusion.value is not None,
            },
        }
