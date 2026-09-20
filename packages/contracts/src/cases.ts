import type { DataProvenance } from "./provenance";

export type CaseStatus =
  "created" | "mesh_uploaded" | "mesh_validated" | "mesh_rejected" | "plan_generated";

export interface MeshAsset {
  arch: "upper" | "lower";
  file_path: string;
  original_filename: string;
  uploaded_at: string;
}

export interface Case {
  id: string;
  patient_reference: string;
  status: CaseStatus;
  meshes: MeshAsset[];
  created_at: string;
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
