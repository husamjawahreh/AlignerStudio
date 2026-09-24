import type { Case, MeshValidationResult, TreatmentPlan } from "@alignerstudio/contracts";
import type { MovementSummary, ReviewBundle } from "../review/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 180000);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { ...init, signal: controller.signal });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Request to ${path} failed (${response.status}): ${body}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`The case analysis is still running. Request timed out while waiting for ${path}.`);
    }
    if (error instanceof TypeError && error.message === "Failed to fetch") {
      throw new Error(`The API connection was interrupted while requesting ${path}. Check that the local API is running.`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export interface DemoTreatmentResponse {
  case: Case;
  review_bundle: ReviewBundle;
}

export interface ExportDownload {
  blob: Blob;
  manifest: Record<string, unknown> | null;
  filename: string;
}

export interface ProcessingStatus {
  job_id: string;
  case_id: string;
  overall_progress: number;
  current_stage: string;
  stage_status: "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED";
  stage_progress: number | null;
  completed_stages: string[];
  pending_stages: string[];
  error_state: boolean;
  error_code: string | null;
  user_message: string;
  technical_diagnostic?: string | null;
  started_at: string;
  updated_at: string;
  completed_at: string | null;
  elapsed_seconds?: number;
  upper_status?: string;
  lower_status?: string;
  planning_status?: string;
}

export interface PipelineDiagnostic {
  state:
    | "model_unavailable"
    | "segmentation_failed"
    | "identification_incomplete"
    | "planning_unavailable"
    | "planning_ready";
  source_kind: "uploaded_real_case" | "validated_real_case";
  segmentation_runtime_ms: number | null;
  total_runtime_ms: number;
  tooth_instance_count: number;
  identification_confidence: number | null;
  identified_teeth: number;
  uncertain_teeth: number;
  unidentified_teeth: number;
  validation_findings: string[];
  failures: string[];
  arch_analysis_available: boolean;
  notes: string[];
  provenance?: "real" | "generated" | "experimental" | "fixture" | "clinically_reviewed";
  fixture?: boolean;
  experimental?: boolean;
  fdi_assignments?: [number, number | null][];
  duplicate_fdi_numbers?: number[];
  missing_fdi_numbers?: number[];
  excluded_fragment_count?: number;
  tooth_instances?: PipelineToothInstance[];
}

export interface PipelineToothInstance {
  instance_id: number;
  fdi_number: number | null;
  tooth_ref?: string | null;
  semantic_label?: number | null;
  planning_mode?: "clinical_fdi" | "semantic_only_experimental";
  arch: "upper" | "lower";
  vertices: [number, number, number][];
  faces: [number, number, number][];
  centroid: [number, number, number];
  confidence: number;
  provenance: "real" | "generated" | "experimental" | "fixture" | "clinically_reviewed";
  fixture: boolean;
  experimental: boolean;
}

export const api = {
  createCase(patientReference: string): Promise<Case> {
    return requestJson<Case>("/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_reference: patientReference }),
    });
  },

  getCase(caseId: string): Promise<Case> {
    return requestJson<Case>(`/cases/${caseId}`);
  },

  async uploadMesh(caseId: string, arch: "upper" | "lower", file: File): Promise<Case> {
    const formData = new FormData();
    formData.append("file", file);
    return requestJson<Case>(`/cases/${caseId}/uploads?arch=${arch}`, {
      method: "POST",
      body: formData,
    });
  },

  removeMesh(caseId: string, arch: "upper" | "lower"): Promise<Case> {
    return requestJson<Case>(`/cases/${caseId}/uploads/${arch}`, { method: "DELETE" });
  },

  validateMesh(caseId: string, arch: "upper" | "lower"): Promise<MeshValidationResult> {
    return requestJson<MeshValidationResult>(`/cases/${caseId}/uploads/${arch}/validate`, {
      method: "POST",
    });
  },

  processPipeline(caseId: string, arch: "upper" | "lower"): Promise<PipelineDiagnostic> {
    return requestJson<PipelineDiagnostic>(`/cases/${caseId}/pipeline/${arch}`, { method: "POST" });
  },

  generatePlan(caseId: string): Promise<TreatmentPlan> {
    return requestJson<TreatmentPlan>(`/cases/${caseId}/plan`, { method: "POST" });
  },

  startProcessing(caseId: string): Promise<ProcessingStatus> {
    return requestJson<ProcessingStatus>(`/cases/${caseId}/processing`, { method: "POST" });
  },

  getProcessingStatus(caseId: string): Promise<ProcessingStatus> {
    return requestJson<ProcessingStatus>(`/cases/${caseId}/processing-status`);
  },

  createEngineeringDemo(): Promise<DemoTreatmentResponse> {
    return requestJson<DemoTreatmentResponse>("/cases/demo", { method: "POST" });
  },

  getTreatment(caseId: string): Promise<ReviewBundle> {
    return requestJson<ReviewBundle>(`/cases/${caseId}/treatment`);
  },

  applyTreatmentEdit(
    caseId: string,
    toothNumber: number | string,
    movement: MovementSummary,
  ): Promise<ReviewBundle> {
    return requestJson<ReviewBundle>(`/cases/${caseId}/treatment/edits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...(typeof toothNumber === "string" && toothNumber.includes(":instance:")
          ? { tooth_ref: toothNumber }
          : { tooth_number: Number(toothNumber) }),
        translation_x: movement.translationX,
        translation_y: movement.translationY,
        translation_z: movement.translationZ,
        rotation: movement.rotation,
        tip: movement.tip,
        torque: movement.torque,
        intrusion: movement.intrusion,
        extrusion: movement.extrusion,
        locked: movement.locked ?? false,
        excluded: movement.excluded ?? false,
      }),
    });
  },

  recalculateTreatment(caseId: string): Promise<ReviewBundle> {
    return requestJson<ReviewBundle>(`/cases/${caseId}/treatment/recalculate`, {
      method: "POST",
    });
  },

  async exportTreatment(caseId: string): Promise<ExportDownload> {
    const response = await fetch(`${API_BASE_URL}/cases/${caseId}/export`, { method: "POST" });
    if (!response.ok)
      throw new Error(`Export failed (${response.status}): ${await response.text()}`);
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const filename = disposition.match(/filename="?([^";]+)"?/)?.[1] ?? "alignerstudio-export.zip";
    const manifestHeader = response.headers.get("X-AlignerStudio-Manifest");
    return {
      blob: await response.blob(),
      manifest: manifestHeader ? (JSON.parse(manifestHeader) as Record<string, unknown>) : null,
      filename,
    };
  },
};
