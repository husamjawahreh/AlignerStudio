/** P3 anatomical intelligence contracts — honest availability, no invented anatomy. */

export type Vector3TupleArray = [number, number, number];

export type AnatomyExtent = "crown_only_stl" | "root_bone_cbct";

export type OcclusionAvailability = "unavailable" | "requires_review" | "computed";

export interface ToothLandmarksPayload {
  centroid: Vector3TupleArray;
  mesial_point: Vector3TupleArray;
  distal_point: Vector3TupleArray;
  occlusal_point: Vector3TupleArray;
  gingival_point: Vector3TupleArray;
}

export interface ToothCoordinateSystemPayload {
  origin: Vector3TupleArray;
  lateral_axis: Vector3TupleArray;
  anterior_axis: Vector3TupleArray;
  vertical_axis: Vector3TupleArray;
  semantics: string[];
}

export interface ArchMeasurementsPayload {
  arch: "upper" | "lower";
  centerline: Array<{ instance_id: number; point: Vector3TupleArray | null }>;
  ordered_instance_ids: number[];
  total_width: number;
  left_half_width: number;
  right_half_width: number;
  anterior_width: number | null;
  posterior_width: number | null;
  consecutive_tooth_distances: number[];
  anterior_to_posterior_order: number[];
  orientation_lateral_axis: Vector3TupleArray | null;
  orientation_anterior_axis: Vector3TupleArray | null;
  orientation_vertical_axis: Vector3TupleArray | null;
  geometric_midline_point: Vector3TupleArray | null;
  provenance: string;
  fixture: boolean;
  notes: string;
}

export interface OcclusionRepresentationPayload {
  availability: OcclusionAvailability;
  upper_lower_registration: OcclusionAvailability;
  occlusal_relationship: OcclusionAvailability;
  bite_record: OcclusionAvailability;
  occlusal_contacts: OcclusionAvailability;
  contact_count: number | null;
  notes: string[];
  provenance: string;
  fixture: boolean;
}

export interface DataQualityReportPayload {
  scale_validation: string;
  units: string;
  mesh_quality: string;
  incomplete_scans: boolean;
  missing_teeth: boolean;
  ambiguous_identity: boolean;
  incomplete_occlusion: boolean;
  missing_anatomy: boolean;
  anatomy_extent: AnatomyExtent;
  findings: string[];
  provenance: string;
  fixture: boolean;
  requires_review: boolean;
}

export interface AnatomicalIntelligencePayload {
  anatomy_extent: AnatomyExtent;
  landmarks_available: boolean;
  local_axes_available: boolean;
  movement_frames_available: boolean;
  arch_orientation_available: boolean;
  arch_form_available: boolean;
  midline_available: boolean;
  occlusion: OcclusionRepresentationPayload;
  data_quality: DataQualityReportPayload;
}
