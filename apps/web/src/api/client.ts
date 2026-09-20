import type { Case, MeshValidationResult, TreatmentPlan } from "@alignerstudio/contracts";
import type { MovementSummary, ReviewBundle } from "../review/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request to ${path} failed (${response.status}): ${body}`);
  }
  return (await response.json()) as T;
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

export interface PipelineDiagnostic {
  state:
    | "model_unavailable"
    | "segmentation_failed"
    | "identification_incomplete"
    | "planning_unavailable"
    | "planning_ready";
  source_kind: "uploaded_real_case";
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
}

export const api = {
  createCase(patientReference: string): Promise<Case> {
    return requestJson<Case>("/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_reference: patientReference }),
    });
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

  createEngineeringDemo(): Promise<DemoTreatmentResponse> {
    return requestJson<DemoTreatmentResponse>("/cases/demo", { method: "POST" });
  },

  getTreatment(caseId: string): Promise<ReviewBundle> {
    return requestJson<ReviewBundle>(`/cases/${caseId}/treatment`);
  },

  applyTreatmentEdit(
    caseId: string,
    toothNumber: number,
    movement: MovementSummary,
  ): Promise<ReviewBundle> {
    return requestJson<ReviewBundle>(`/cases/${caseId}/treatment/edits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tooth_number: toothNumber,
        translation_x: movement.translationX,
        translation_y: movement.translationY,
        translation_z: movement.translationZ,
        rotation: movement.rotation,
        tip: movement.tip,
        torque: movement.torque,
        intrusion: movement.intrusion,
        extrusion: movement.extrusion,
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
