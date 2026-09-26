import type { DataProvenance } from "./provenance";

export type CaseStatus =
  "created" | "mesh_uploaded" | "mesh_validated" | "mesh_rejected" | "plan_generated";

export interface MeshAsset {
  arch: "upper" | "lower";
  file_path: string;
  original_filename: string;
  uploaded_at: string;
}

export interface PreparationJob {
  job_id: string;
  case_id?: string;
  arch?: string;
  source_artifact_hash?: string;
  operation?: string;
  parameters?: Record<string, unknown>;
  mode?: string;
  state?: "queued" | "running" | "completed" | "failed" | "cancelled";
  queued_at?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  duration_ms?: number | null;
  progress?: number | null;
  progress_stage?: string | null;
  output_artifact_hash?: string | null;
  error?: { code?: string; message?: string } | null;
  cache_hit?: boolean;
  reused?: boolean;
  duplicate?: boolean;
  result?: Record<string, unknown> | null;
  clinical_axes?: boolean;
}

export interface PreparationOperation {
  operation?: string;
  truth_state?: string;
  clinical_axes?: boolean;
}

export interface PreparationQualitySide {
  vertex_count?: number;
  face_count?: number;
  warnings?: string[];
  blockers?: string[];
}

export interface PreparationState {
  readiness?: string;
  version?: number;
  operations?: PreparationOperation[];
  quality_comparison?: {
    source?: PreparationQualitySide;
    prepared?: PreparationQualitySide;
  } | null;
  active?: {
    output_sha256?: string;
    role?: string;
    truth_state?: string;
    observed_anatomy?: boolean;
  } | null;
  fdi_assigned?: boolean;
  occlusion_established?: boolean;
  clinical_axes?: boolean;
  clinically_segmented?: boolean;
  future_segmentation_input?: {
    uses_derived_hash_as_source?: boolean;
    uses_prepared_mesh?: boolean;
  };
  components?: Array<{ id: number; face_count: number; vertex_count?: number }>;
}

export interface SegmentationJob {
  job_id: string;
  case_id?: string;
  arch?: string;
  prepared_input_sha?: string;
  source_sha256?: string;
  backend?: string;
  model_sha256?: string | null;
  state?: "queued" | "running" | "completed" | "failed" | "cancelled";
  queued_at?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  duration_ms?: number | null;
  progress?: number | null;
  progress_stage?: string | null;
  output_run_id?: string | null;
  error?: { code?: string; message?: string; availability?: string } | null;
  blocked?: boolean;
  real_inference?: boolean;
  duplicate?: boolean;
  semantic_identity?: string;
  fdi_assigned?: boolean;
  clinically_segmented?: boolean;
  clinical_accuracy_claim?: boolean;
  self_test_state?: string | null;
  quality_evaluation?: string | null;
  split_available?: boolean;
}

export interface SegmentationInstance {
  instance_id: string;
  raw_model_class?: number | null;
  model_class_label?: string;
  model_class_mapping?: string;
  truth_state?: string;
  review_state?: string;
  visible?: boolean;
  fdi?: number | null;
  real_inference?: boolean;
  confidence?: number | null;
  confidence_available?: boolean;
}

export interface SegmentationState {
  availability?: string | null;
  capability_state?: string | null;
  semantic_identity?: string;
  fdi_assigned?: boolean;
  clinically_segmented?: boolean;
  clinical_accuracy_claim?: boolean;
  self_test_state?: string | null;
  quality_evaluation?: string | null;
  split_available?: boolean;
  active_run?: {
    run_id?: string;
    status?: string;
    reviewable?: boolean;
    real_inference?: boolean;
    prepared_sha256?: string;
    source_sha256?: string;
    inference_kind?: string;
    semantic_identity?: string;
    blocker?: { code?: string; message?: string; availability?: string } | null;
  } | null;
  review?: {
    run_id?: string;
    reviewable?: boolean;
    reason?: string;
    selected_instance_id?: string | null;
    instances?: SegmentationInstance[];
  } | null;
}

export interface IntakeArtifact {
  format?: string;
  readiness?: string;
  vertex_count?: number;
  face_count?: number;
  warnings?: string[];
  blockers?: string[];
  occlusion_established?: boolean;
  fdi_assigned?: boolean;
  arch?: { arch?: string; truth?: string };
  bounding_box?: { min: number[]; max: number[] } | null;
  preparation?: PreparationState | null;
  segmentation?: SegmentationState | null;
}

export interface Case {
  id: string;
  patient_reference: string;
  status: CaseStatus;
  meshes: MeshAsset[];
  created_at: string;
  intake_artifacts?: IntakeArtifact[];
  intake_summary?: {
    upper_present?: boolean;
    lower_present?: boolean;
    occlusion_established?: boolean;
    requires_both_arches?: boolean;
  };
}

export interface MeshValidationResult {
  is_valid: boolean;
  triangle_count: number;
  is_watertight: boolean;
  errors: string[];
}

export interface ToothPosition {
  fdi_number: number;
}

export interface Stage {
  index: number;
  tooth_positions: ToothPosition[];
  provenance: DataProvenance;
  fixture: boolean;
  notes: string;
}

export interface TreatmentPlan {
  id: string;
  case_id: string;
  stages: Stage[];
  provenance: DataProvenance;
  fixture: boolean;
  notes: string;
  created_at: string;
}
