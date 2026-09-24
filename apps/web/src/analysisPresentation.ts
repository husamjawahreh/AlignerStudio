import type { MeshValidationResult } from "@alignerstudio/contracts";
import type { PipelineDiagnostic } from "./api/client";
import type { ReviewToothMesh } from "./review/types";

export interface AnalysisFinding {
  kind: "warning" | "gap" | "note";
  text: string;
}

export interface AnalysisOverview {
  ran: boolean;
  stateLabel: string;
  instanceCount: number;
  upperCount: number;
  lowerCount: number;
  identifiedTeeth: number | null;
  uncertainTeeth: number | null;
  unidentifiedTeeth: number | null;
  archAnalysisAvailable: boolean | null;
  identificationConfidence: number | null;
  landmarksAvailable: boolean | null;
  localAxesAvailable: boolean | null;
  movementFramesAvailable: boolean | null;
  archOrientationAvailable: boolean | null;
  archFormAvailable: boolean | null;
  midlineAvailable: boolean | null;
  occlusionAvailability: string | null;
  anatomyExtent: string | null;
  scaleValidation: string | null;
  units: string | null;
  meshQuality: string | null;
  incompleteScans: boolean | null;
  missingTeeth: boolean | null;
  ambiguousIdentity: boolean | null;
  incompleteOcclusion: boolean | null;
  missingAnatomy: boolean | null;
  archTotalWidth: number | null;
  interToothCount: number | null;
}

/**
 * Build analysis overview from existing pipeline/review data only.
 * Does not invent anatomy, FDI, landmarks, axes, or occlusion.
 */
export function buildAnalysisOverview(input: {
  diagnostic: PipelineDiagnostic | null;
  teeth: readonly ReviewToothMesh[];
}): AnalysisOverview {
  const diagnostic = input.diagnostic;
  const upperCount = input.teeth.filter((tooth) => tooth.arch === "upper").length;
  const lowerCount = input.teeth.filter((tooth) => tooth.arch === "lower").length;
  const intel = diagnostic?.anatomical_intelligence ?? null;
  const arch = diagnostic?.arch_measurements ?? null;
  if (!diagnostic) {
    return {
      ran: false,
      stateLabel: "Not run",
      instanceCount: input.teeth.length,
      upperCount,
      lowerCount,
      identifiedTeeth: null,
      uncertainTeeth: null,
      unidentifiedTeeth: null,
      archAnalysisAvailable: null,
      identificationConfidence: null,
      landmarksAvailable: null,
      localAxesAvailable: null,
      movementFramesAvailable: null,
      archOrientationAvailable: null,
      archFormAvailable: null,
      midlineAvailable: null,
      occlusionAvailability: null,
      anatomyExtent: null,
      scaleValidation: null,
      units: null,
      meshQuality: null,
      incompleteScans: null,
      missingTeeth: null,
      ambiguousIdentity: null,
      incompleteOcclusion: null,
      missingAnatomy: null,
      archTotalWidth: null,
      interToothCount: null,
    };
  }
  const teethHaveLandmarks = (diagnostic.tooth_instances ?? []).some(
    (tooth) => tooth.landmarks != null,
  );
  const teethHaveAxes = (diagnostic.tooth_instances ?? []).some(
    (tooth) => tooth.coordinate_system != null || tooth.movement_reference_frame != null,
  );
  return {
    ran: true,
    stateLabel: diagnostic.state.replaceAll("_", " "),
    instanceCount: diagnostic.tooth_instance_count,
    upperCount,
    lowerCount,
    identifiedTeeth: diagnostic.identified_teeth,
    uncertainTeeth: diagnostic.uncertain_teeth,
    unidentifiedTeeth: diagnostic.unidentified_teeth,
    archAnalysisAvailable: diagnostic.arch_analysis_available,
    identificationConfidence: diagnostic.identification_confidence,
    landmarksAvailable: intel?.landmarks_available ?? teethHaveLandmarks,
    localAxesAvailable: intel?.local_axes_available ?? teethHaveAxes,
    movementFramesAvailable: intel?.movement_frames_available ?? teethHaveAxes,
    archOrientationAvailable: intel?.arch_orientation_available ?? false,
    archFormAvailable: intel?.arch_form_available ?? Boolean(arch),
    midlineAvailable: intel?.midline_available ?? Boolean(arch?.geometric_midline_point),
    occlusionAvailability: intel?.occlusion.availability ?? "unavailable",
    anatomyExtent: intel?.anatomy_extent ?? "crown_only_stl",
    scaleValidation: intel?.data_quality.scale_validation ?? "unverified",
    units: intel?.data_quality.units ?? "unverified",
    meshQuality: intel?.data_quality.mesh_quality ?? null,
    incompleteScans: intel?.data_quality.incomplete_scans ?? null,
    missingTeeth: intel?.data_quality.missing_teeth ?? null,
    ambiguousIdentity: intel?.data_quality.ambiguous_identity ?? null,
    incompleteOcclusion: intel?.data_quality.incomplete_occlusion ?? true,
    missingAnatomy: intel?.data_quality.missing_anatomy ?? true,
    archTotalWidth: arch?.total_width ?? null,
    interToothCount: arch?.consecutive_tooth_distances.length ?? null,
  };
}

/** Tooth identity label: FDI only when genuinely present; otherwise semantic ref. */
export function formatToothIdentity(tooth: {
  fdiNumber?: number | null;
  toothRef?: string | null;
  instanceId: number;
}): string {
  if (tooth.fdiNumber != null) return `FDI ${tooth.fdiNumber}`;
  if (tooth.toothRef) return tooth.toothRef;
  return `instance:${tooth.instanceId}`;
}

export function buildAnalysisFindings(input: {
  diagnostic: PipelineDiagnostic | null;
  validation: MeshValidationResult | null;
}): AnalysisFinding[] {
  const findings: AnalysisFinding[] = [];
  const diagnostic = input.diagnostic;
  if (!diagnostic) {
    findings.push({ kind: "gap", text: "Analysis has not been run for this case." });
    return findings;
  }
  for (const failure of diagnostic.failures ?? []) {
    findings.push({ kind: "warning", text: failure });
  }
  for (const finding of diagnostic.validation_findings ?? []) {
    findings.push({ kind: "warning", text: finding });
  }
  for (const note of diagnostic.notes ?? []) {
    findings.push({ kind: "note", text: note });
  }
  for (const qualityFinding of diagnostic.anatomical_intelligence?.data_quality.findings ?? []) {
    findings.push({ kind: "gap", text: qualityFinding });
  }
  for (const occlusionNote of diagnostic.anatomical_intelligence?.occlusion.notes ?? []) {
    findings.push({ kind: "gap", text: occlusionNote });
  }
  if ((diagnostic.duplicate_fdi_numbers?.length ?? 0) > 0) {
    findings.push({
      kind: "warning",
      text: `Duplicate FDI: ${diagnostic.duplicate_fdi_numbers?.join(", ")}`,
    });
  }
  if ((diagnostic.missing_fdi_numbers?.length ?? 0) > 0) {
    findings.push({
      kind: "gap",
      text: `Missing FDI: ${diagnostic.missing_fdi_numbers?.join(", ")}`,
    });
  }
  if ((diagnostic.excluded_fragment_count ?? 0) > 0) {
    findings.push({
      kind: "note",
      text: `Excluded zero-face fragments: ${diagnostic.excluded_fragment_count}`,
    });
  }
  if (diagnostic.uncertain_teeth > 0) {
    findings.push({
      kind: "gap",
      text: `Uncertain teeth: ${diagnostic.uncertain_teeth}`,
    });
  }
  if (diagnostic.unidentified_teeth > 0) {
    findings.push({
      kind: "gap",
      text: `Unidentified teeth: ${diagnostic.unidentified_teeth}`,
    });
  }
  if (input.validation && !input.validation.is_valid) {
    findings.push({ kind: "warning", text: "Latest mesh validation reported an invalid mesh." });
  }
  if (findings.length === 0) {
    findings.push({ kind: "note", text: "No analysis warnings or data gaps were reported." });
  }
  return findings;
}

export function formatAvailability(available: boolean | null, detailWhenAvailable?: string): string {
  if (available === null) return "Unavailable";
  if (!available) return "Unavailable";
  return detailWhenAvailable ?? "Available";
}

export function formatMeshMeasurement(validation: MeshValidationResult | null): string {
  if (!validation) return "Unavailable";
  return `${validation.triangle_count.toLocaleString()} triangles`;
}

export function formatOcclusionAvailability(value: string | null): string {
  if (!value) return "Unavailable";
  return value.replaceAll("_", " ");
}
