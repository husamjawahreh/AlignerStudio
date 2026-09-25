/** Dental Intelligence 2.0 contracts — truth-preserving clinical intelligence (WP-02). */

export type IntelligenceTruthState =
  | "verified"
  | "computed"
  | "requires_review"
  | "not_available";

export interface TruthValuePayload<T = unknown> {
  state: IntelligenceTruthState;
  value: T | null;
  reason: string | null;
  algorithm: string | null;
  algorithm_version: string | null;
}

export interface CapabilityReadinessPayload {
  identity_readiness: IntelligenceTruthState;
  geometry_readiness: IntelligenceTruthState;
  axis_readiness: IntelligenceTruthState;
  occlusion_readiness: IntelligenceTruthState;
  treatment_setup_readiness: IntelligenceTruthState;
  validation_readiness: IntelligenceTruthState;
  reasons: string[];
}

export interface ToothIntelligencePayload {
  instance_id: number;
  tooth_ref: string | null;
  arch: string | null;
  fdi_number: TruthValuePayload<number>;
  semantic_label: TruthValuePayload<number>;
  identification_status: string | null;
  identification_confidence: number | null;
  geometry: TruthValuePayload<Record<string, unknown>>;
  crown_geometry: TruthValuePayload<boolean>;
  root_geometry: TruthValuePayload<boolean>;
  landmarks: TruthValuePayload<Record<string, unknown>>;
  local_coordinate_frame: TruthValuePayload<Record<string, unknown>>;
  clinical_dental_axes: TruthValuePayload<Record<string, unknown>>;
  mesh_principal_directions: TruthValuePayload<number[][]>;
  quality_findings: string[];
  overall_truth_state: IntelligenceTruthState;
  provenance: string;
  fixture: boolean;
  source_mesh_path?: string | null;
  source_mesh_sha256?: string | null;
  model_name?: string | null;
  model_version?: string | null;
}

export interface ArchIntelligencePayload {
  arch: string;
  tooth_instance_count: number;
  resolved_fdi_count: number;
  unresolved_identity_count: number;
  geometry_ready_count: number;
  landmarks_available_count: number;
  clinical_axes_available_count: number;
  quality_findings: string[];
  overall_truth_state: IntelligenceTruthState;
  provenance: string;
  fixture: boolean;
  source_mesh_path?: string | null;
  source_mesh_sha256?: string | null;
}

export interface CaseDentalIntelligencePayload {
  contract_version: string;
  case_id: string;
  job_id: string | null;
  input_hash: string | null;
  processing_mode: string | null;
  generated_at: string;
  teeth: ToothIntelligencePayload[];
  arches: ArchIntelligencePayload[];
  occlusion: TruthValuePayload<Record<string, unknown>>;
  data_quality_findings: string[];
  capability_readiness: CapabilityReadinessPayload;
  overall_truth_state: IntelligenceTruthState;
  provenance: string;
  fixture: boolean;
  model_name?: string | null;
  model_version?: string | null;
  timings_ms?: Record<string, number | null>;
  limitations?: string[];
  counts?: {
    tooth_instances: number;
    resolved_fdi: number;
    unresolved_identity: number;
    arch_assigned: number;
    clinical_axes_available: number;
    landmarks_available: number;
    occlusion_available: boolean;
  };
}
