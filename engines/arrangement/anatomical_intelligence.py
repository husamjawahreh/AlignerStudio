"""P3 anatomical intelligence assembly — serialize existing evidence only."""

from __future__ import annotations

from dataclasses import dataclass

from domain.case.provenance import DataProvenance
from domain.tooth.anatomy_extent import AnatomyExtent, default_anatomy_extent_for_stl
from domain.tooth.arch import ArchMeasurements
from domain.tooth.data_quality import DataQualityReport
from domain.tooth.identification import IdentifiedTooth, ToothIdentificationResult
from domain.tooth.occlusion import OcclusionRepresentation, unavailable_occlusion


def serialize_vector3(value: tuple[float, float, float] | None) -> list[float] | None:
    if value is None:
        return None
    return [float(value[0]), float(value[1]), float(value[2])]


def serialize_landmarks(tooth: IdentifiedTooth) -> dict | None:
    if tooth.landmarks is None:
        return None
    landmarks = tooth.landmarks
    return {
        "centroid": serialize_vector3(landmarks.centroid),
        "mesial_point": serialize_vector3(landmarks.mesial_point),
        "distal_point": serialize_vector3(landmarks.distal_point),
        "occlusal_point": serialize_vector3(landmarks.occlusal_point),
        "gingival_point": serialize_vector3(landmarks.gingival_point),
    }


def serialize_coordinate_system(tooth: IdentifiedTooth) -> dict | None:
    if tooth.coordinate_system is None:
        return None
    frame = tooth.coordinate_system
    return {
        "origin": serialize_vector3(frame.origin),
        "lateral_axis": serialize_vector3(frame.lateral_axis),
        "anterior_axis": serialize_vector3(frame.anterior_axis),
        "vertical_axis": serialize_vector3(frame.vertical_axis),
        "semantics": list(frame.semantics),
    }


def serialize_identified_tooth(tooth: IdentifiedTooth) -> dict:
    """Serialize one tooth with identity/frame evidence — never invent FDI."""
    coordinate_system = serialize_coordinate_system(tooth)
    return {
        "instance_id": tooth.instance.instance_id,
        "fdi_number": tooth.identity.number if tooth.identity else None,
        "tooth_ref": tooth.tooth_ref or tooth.instance.tooth_ref,
        "semantic_label": tooth.semantic_label
        if tooth.semantic_label is not None
        else tooth.instance.semantic_label,
        "planning_mode": tooth.planning_mode,
        "arch": tooth.instance.arch
        if tooth.instance.arch
        else (tooth.identity.arch.value if tooth.identity else None),
        "vertices": tooth.instance.mesh_vertices,
        "faces": tooth.instance.mesh_faces,
        "centroid": tooth.instance.centroid,
        "confidence": tooth.confidence.score if tooth.confidence_available else None,
        "confidence_available": tooth.confidence_available,
        "identification_status": tooth.confidence.status.value,
        "identification_reasons": list(tooth.confidence.reasons),
        "landmarks": serialize_landmarks(tooth),
        "coordinate_system": coordinate_system,
        "movement_reference_frame": coordinate_system,
        "provenance": tooth.provenance.value,
        "fixture": tooth.fixture,
        "experimental": tooth.provenance
        in (DataProvenance.EXPERIMENTAL, DataProvenance.FIXTURE, DataProvenance.GENERATED),
        "anatomy_extent": default_anatomy_extent_for_stl().value,
    }


def serialize_arch_measurements(measurements: ArchMeasurements | None) -> dict | None:
    if measurements is None:
        return None
    return {
        "arch": measurements.arch.value,
        "centerline": [
            {"instance_id": point.instance_id, "point": serialize_vector3(point.point)}
            for point in measurements.centerline
        ],
        "ordered_instance_ids": list(measurements.ordered_instance_ids),
        "total_width": measurements.total_width,
        "left_half_width": measurements.left_half_width,
        "right_half_width": measurements.right_half_width,
        "anterior_width": measurements.anterior_width,
        "posterior_width": measurements.posterior_width,
        "consecutive_tooth_distances": list(measurements.consecutive_tooth_distances),
        "anterior_to_posterior_order": list(measurements.anterior_to_posterior_order),
        "orientation_lateral_axis": serialize_vector3(measurements.orientation_lateral_axis),
        "orientation_anterior_axis": serialize_vector3(measurements.orientation_anterior_axis),
        "orientation_vertical_axis": serialize_vector3(measurements.orientation_vertical_axis),
        "geometric_midline_point": serialize_vector3(measurements.geometric_midline_point),
        "provenance": measurements.provenance.value,
        "fixture": measurements.fixture,
        "notes": measurements.notes,
    }


@dataclass(frozen=True)
class AnatomicalIntelligenceSummary:
    """P3 summary block attached to pipeline diagnostics."""

    anatomy_extent: AnatomyExtent
    landmarks_available: bool
    local_axes_available: bool
    movement_frames_available: bool
    arch_orientation_available: bool
    arch_form_available: bool
    midline_available: bool
    occlusion: OcclusionRepresentation
    data_quality: DataQualityReport

    def payload(self) -> dict:
        return {
            "anatomy_extent": self.anatomy_extent.value,
            "landmarks_available": self.landmarks_available,
            "local_axes_available": self.local_axes_available,
            "movement_frames_available": self.movement_frames_available,
            "arch_orientation_available": self.arch_orientation_available,
            "arch_form_available": self.arch_form_available,
            "midline_available": self.midline_available,
            "occlusion": self.occlusion.payload(),
            "data_quality": self.data_quality.payload(),
        }


def build_data_quality_report(
    *,
    identification: ToothIdentificationResult | None,
    arch_measurements: ArchMeasurements | None,
    mesh_is_valid: bool | None,
    mesh_is_watertight: bool | None,
    triangle_count: int | None,
    incomplete_scans: bool,
    provenance: DataProvenance,
    fixture: bool,
) -> DataQualityReport:
    findings: list[str] = []
    ambiguous = False
    missing_teeth = False
    if identification is not None:
        ambiguous = bool(identification.uncertain or identification.unidentified)
        missing_teeth = bool(identification.unidentified)
        if identification.uncertain:
            findings.append(f"Ambiguous identity: {len(identification.uncertain)} uncertain teeth.")
        if identification.unidentified:
            findings.append(
                f"Missing/unidentified teeth: {len(identification.unidentified)} instances."
            )
    if arch_measurements is None:
        findings.append("Arch form / orientation measurements unavailable.")
    findings.append("Occlusion incomplete: no bite record or registration evidence.")
    findings.append("Missing anatomy: roots, bone, and periodontal structures are not in STL.")
    findings.append("Scale/units unverified for clinical measurement use.")

    if mesh_is_valid is False:
        mesh_quality = "invalid"
        findings.append("Mesh validation reported an invalid mesh.")
    elif mesh_is_valid is True:
        mesh_quality = "watertight" if mesh_is_watertight else "non_watertight"
        if triangle_count is not None:
            findings.append(f"Mesh triangle count: {triangle_count}.")
    else:
        mesh_quality = "unverified"

    if incomplete_scans:
        findings.append("Incomplete scans: one or both arches missing or not ready.")

    return DataQualityReport(
        scale_validation="unverified",
        units="unverified",
        mesh_quality=mesh_quality,
        incomplete_scans=incomplete_scans,
        missing_teeth=missing_teeth,
        ambiguous_identity=ambiguous,
        incomplete_occlusion=True,
        missing_anatomy=True,
        anatomy_extent=default_anatomy_extent_for_stl(),
        findings=tuple(findings),
        provenance=provenance,
        fixture=fixture,
        requires_review=True,
    )


def build_anatomical_intelligence_summary(
    *,
    identification: ToothIdentificationResult | None,
    arch_measurements: ArchMeasurements | None = None,
    mesh_is_valid: bool | None = None,
    mesh_is_watertight: bool | None = None,
    triangle_count: int | None = None,
    incomplete_scans: bool = False,
) -> AnatomicalIntelligenceSummary:
    teeth = identification.teeth if identification else ()
    landmarks_available = any(tooth.landmarks is not None for tooth in teeth)
    axes_available = any(tooth.coordinate_system is not None for tooth in teeth)
    provenance = (
        identification.provenance if identification else DataProvenance.EXPERIMENTAL
    )
    fixture = identification.fixture if identification else False
    occlusion = unavailable_occlusion(provenance=provenance, fixture=fixture)
    data_quality = build_data_quality_report(
        identification=identification,
        arch_measurements=arch_measurements,
        mesh_is_valid=mesh_is_valid,
        mesh_is_watertight=mesh_is_watertight,
        triangle_count=triangle_count,
        incomplete_scans=incomplete_scans,
        provenance=provenance,
        fixture=fixture,
    )
    return AnatomicalIntelligenceSummary(
        anatomy_extent=default_anatomy_extent_for_stl(),
        landmarks_available=landmarks_available,
        local_axes_available=axes_available,
        movement_frames_available=axes_available,
        arch_orientation_available=bool(
            arch_measurements
            and arch_measurements.orientation_lateral_axis is not None
        ),
        arch_form_available=arch_measurements is not None,
        midline_available=bool(
            arch_measurements and arch_measurements.geometric_midline_point is not None
        ),
        occlusion=occlusion,
        data_quality=data_quality,
    )
