import type {
  CaseDentalIntelligencePayload,
  IntelligenceTruthState,
  MeshValidationResult,
} from "@alignerstudio/contracts";
import type { PipelineDiagnostic } from "./api/client";
import type { ReviewToothMesh } from "./review/types";
import { PRODUCT_TRUTH_LABELS, type ProductTruthState } from "./design-system/truthState";

export interface AnalysisFinding {
  kind: "warning" | "gap" | "note";
  text: string;
}

export interface AnalysisOverview {
  ran: boolean;
  stateLabel: string;
  /** False when segmentation did not run or failed. Counts must not read as a clinical zero. */
  countsAvailable: boolean;
  segmentationTruthState: string | null;
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
  /** WP-02 Dental Intelligence 2.0 truth states (null when document absent). */
  intelligenceContractVersion: string | null;
  overallTruthState: IntelligenceTruthState | null;
  clinicalAxesTruth: IntelligenceTruthState | null;
  landmarksTruth: IntelligenceTruthState | null;
  rootsTruth: IntelligenceTruthState | null;
  occlusionTruth: IntelligenceTruthState | null;
  identityReadiness: IntelligenceTruthState | null;
  geometryReadiness: IntelligenceTruthState | null;
  axisReadiness: IntelligenceTruthState | null;
  occlusionReadiness: IntelligenceTruthState | null;
  treatmentSetupReadiness: IntelligenceTruthState | null;
  validationReadiness: IntelligenceTruthState | null;
  readinessReasons: string[];
  dataQualityFindings: string[];
  limitations: string[];
  /** WP-08 capability detail (null when absent). */
  occlusionCapabilityState: string | null;
  registrationState: string | null;
  geometricContactCount: number | null;
  crownAnatomyState: string | null;
  rootAnatomyState: string | null;
  landmarkAnatomyState: string | null;
  clinicalAxesAnatomyState: string | null;
  genericGeometricAxesState: string | null;
  cbctAnatomyState: string | null;
  occlusionValidated: false | null;
}

/**
 * Build analysis overview from existing pipeline/review data only.
 * Does not invent anatomy, FDI, landmarks, axes, or occlusion.
 * Prefer Dental Intelligence 2.0 truth states when present.
 */
export function buildAnalysisOverview(input: {
  diagnostic: PipelineDiagnostic | null;
  teeth: readonly ReviewToothMesh[];
  dentalIntelligence?: CaseDentalIntelligencePayload | null;
}): AnalysisOverview {
  const diagnostic = input.diagnostic;
  const intelDoc =
    input.dentalIntelligence ?? diagnostic?.dental_intelligence ?? null;
  const upperCount = input.teeth.filter((tooth) => tooth.arch === "upper").length;
  const lowerCount = input.teeth.filter((tooth) => tooth.arch === "lower").length;
  const intel = diagnostic?.anatomical_intelligence ?? null;
  const arch = diagnostic?.arch_measurements ?? null;
  const emptyIntelFields = {
    intelligenceContractVersion: null as string | null,
    overallTruthState: null as IntelligenceTruthState | null,
    clinicalAxesTruth: null as IntelligenceTruthState | null,
    landmarksTruth: null as IntelligenceTruthState | null,
    rootsTruth: null as IntelligenceTruthState | null,
    occlusionTruth: null as IntelligenceTruthState | null,
    identityReadiness: null as IntelligenceTruthState | null,
    geometryReadiness: null as IntelligenceTruthState | null,
    axisReadiness: null as IntelligenceTruthState | null,
    occlusionReadiness: null as IntelligenceTruthState | null,
    treatmentSetupReadiness: null as IntelligenceTruthState | null,
    validationReadiness: null as IntelligenceTruthState | null,
    readinessReasons: [] as string[],
    dataQualityFindings: [] as string[],
    limitations: [] as string[],
    occlusionCapabilityState: null as string | null,
    registrationState: null as string | null,
    geometricContactCount: null as number | null,
    crownAnatomyState: null as string | null,
    rootAnatomyState: null as string | null,
    landmarkAnatomyState: null as string | null,
    clinicalAxesAnatomyState: null as string | null,
    genericGeometricAxesState: null as string | null,
    cbctAnatomyState: null as string | null,
    occlusionValidated: null as false | null,
  };
  if (!diagnostic && !intelDoc) {
    return {
      ran: false,
      stateLabel: "Not run",
      countsAvailable: false,
      segmentationTruthState: null,
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
      ...emptyIntelFields,
    };
  }

  const teethHaveLandmarks = (diagnostic?.tooth_instances ?? []).some(
    (tooth) => tooth.landmarks != null,
  );
  const teethHaveAxes = (diagnostic?.tooth_instances ?? []).some(
    (tooth) => tooth.coordinate_system != null || tooth.movement_reference_frame != null,
  );

  const intelFields = intelDoc
    ? (() => {
        const occValue = (intelDoc.occlusion.value ?? {}) as Record<string, unknown>;
        const anatomy = (occValue.advanced_anatomy ?? null) as Record<string, unknown> | null;
        const registration = (occValue.registration ?? null) as Record<string, unknown> | null;
        const contacts = Array.isArray(occValue.contact_candidates)
          ? occValue.contact_candidates
          : [];
        return {
          intelligenceContractVersion: intelDoc.contract_version,
          overallTruthState: intelDoc.overall_truth_state,
          clinicalAxesTruth: _dominantToothState(
            intelDoc.teeth.map((tooth) => tooth.clinical_dental_axes.state),
          ),
          landmarksTruth: _dominantToothState(
            intelDoc.teeth.map((tooth) => tooth.landmarks.state),
          ),
          rootsTruth: _dominantToothState(
            intelDoc.teeth.map((tooth) => tooth.root_geometry.state),
          ),
          occlusionTruth: intelDoc.occlusion.state,
          identityReadiness: intelDoc.capability_readiness.identity_readiness,
          geometryReadiness: intelDoc.capability_readiness.geometry_readiness,
          axisReadiness: intelDoc.capability_readiness.axis_readiness,
          occlusionReadiness: intelDoc.capability_readiness.occlusion_readiness,
          treatmentSetupReadiness: intelDoc.capability_readiness.treatment_setup_readiness,
          validationReadiness: intelDoc.capability_readiness.validation_readiness,
          readinessReasons: intelDoc.capability_readiness.reasons,
          dataQualityFindings: intelDoc.data_quality_findings,
          limitations: intelDoc.limitations ?? [],
          occlusionCapabilityState:
            typeof occValue.capability_state === "string" ? occValue.capability_state : null,
          registrationState:
            typeof registration?.truth_state === "string" ? registration.truth_state : null,
          geometricContactCount: contacts.length,
          crownAnatomyState:
            typeof anatomy?.crown_geometry === "string" ? anatomy.crown_geometry : null,
          rootAnatomyState:
            typeof anatomy?.root_geometry === "string" ? anatomy.root_geometry : null,
          landmarkAnatomyState:
            typeof anatomy?.landmark_geometry === "string" ? anatomy.landmark_geometry : null,
          clinicalAxesAnatomyState:
            typeof anatomy?.clinical_axes === "string" ? anatomy.clinical_axes : null,
          genericGeometricAxesState:
            typeof anatomy?.generic_geometric_axes === "string"
              ? anatomy.generic_geometric_axes
              : null,
          cbctAnatomyState:
            typeof anatomy?.cbct_volumetric_anatomy === "string"
              ? anatomy.cbct_volumetric_anatomy
              : null,
          occlusionValidated: false as const,
        };
      })()
    : emptyIntelFields;

  // Prefer explicit DI2 truth over boolean availability flags.
  const landmarksAvailable =
    intelFields.landmarksTruth != null
      ? intelFields.landmarksTruth === "verified" || intelFields.landmarksTruth === "computed"
      : (intel?.landmarks_available ?? teethHaveLandmarks);
  const localAxesAvailable =
    intelFields.clinicalAxesTruth != null
      ? intelFields.clinicalAxesTruth === "verified" ||
        intelFields.clinicalAxesTruth === "computed"
      : (intel?.local_axes_available ?? teethHaveAxes);
  const occlusionAvailability =
    intelFields.occlusionTruth ?? intel?.occlusion.availability ?? "unavailable";

  const segmentationTruthState = diagnostic?.segmentation_truth_state ?? null;
  const blocked =
    diagnostic?.state === "blocked_by_environment" ||
    segmentationTruthState === "blocked_by_environment";
  const failed =
    diagnostic?.state === "segmentation_failed" || segmentationTruthState === "failed";
  const unavailable =
    diagnostic?.state === "model_unavailable" || segmentationTruthState === "not_available";
  const countsAvailable = Boolean(diagnostic) && !blocked && !failed && !unavailable;
  let stateLabel = diagnostic
    ? diagnostic.state.replaceAll("_", " ")
    : (intelDoc?.overall_truth_state.replaceAll("_", " ") ?? "Available");
  if (blocked) stateLabel = "Blocked by environment";
  else if (failed) stateLabel = "Failed";
  else if (unavailable) stateLabel = "Not available";
  else if (segmentationTruthState === "requires_review") stateLabel = "Requires review";
  else if (segmentationTruthState === "computed") stateLabel = "Computed";
  else if (segmentationTruthState === "verified") stateLabel = "Verified";

  return {
    ran: true,
    stateLabel,
    countsAvailable,
    segmentationTruthState,
    instanceCount: countsAvailable
      ? (diagnostic?.tooth_instance_count ?? intelDoc?.counts?.tooth_instances ?? input.teeth.length)
      : 0,
    upperCount,
    lowerCount,
    identifiedTeeth: diagnostic?.identified_teeth ?? null,
    uncertainTeeth: diagnostic?.uncertain_teeth ?? null,
    unidentifiedTeeth: diagnostic?.unidentified_teeth ?? null,
    archAnalysisAvailable: diagnostic?.arch_analysis_available ?? null,
    identificationConfidence: diagnostic?.identification_confidence ?? null,
    landmarksAvailable,
    localAxesAvailable,
    movementFramesAvailable: intel?.movement_frames_available ?? teethHaveAxes,
    archOrientationAvailable: intel?.arch_orientation_available ?? false,
    archFormAvailable: intel?.arch_form_available ?? Boolean(arch),
    midlineAvailable: intel?.midline_available ?? Boolean(arch?.geometric_midline_point),
    occlusionAvailability,
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
    ...intelFields,
  };
}

function _dominantToothState(
  states: IntelligenceTruthState[],
): IntelligenceTruthState | null {
  if (states.length === 0) return null;
  if (states.every((state) => state === "not_available")) return "not_available";
  if (states.some((state) => state === "verified")) return "verified";
  if (states.some((state) => state === "computed")) return "computed";
  if (states.some((state) => state === "requires_review")) return "requires_review";
  return "not_available";
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
  dentalIntelligence?: CaseDentalIntelligencePayload | null;
}): AnalysisFinding[] {
  const findings: AnalysisFinding[] = [];
  const diagnostic = input.diagnostic;
  const intelDoc =
    input.dentalIntelligence ?? diagnostic?.dental_intelligence ?? null;
  if (!diagnostic && !intelDoc) {
    findings.push({ kind: "gap", text: "Analysis has not been run for this case." });
    return findings;
  }
  for (const failure of diagnostic?.failures ?? []) {
    findings.push({ kind: "warning", text: failure });
  }
  for (const finding of diagnostic?.validation_findings ?? []) {
    findings.push({ kind: "warning", text: finding });
  }
  for (const note of diagnostic?.notes ?? []) {
    findings.push({ kind: "note", text: note });
  }
  for (const qualityFinding of diagnostic?.anatomical_intelligence?.data_quality.findings ?? []) {
    findings.push({ kind: "gap", text: qualityFinding });
  }
  for (const qualityFinding of intelDoc?.data_quality_findings ?? []) {
    findings.push({ kind: "gap", text: qualityFinding });
  }
  for (const occlusionNote of diagnostic?.anatomical_intelligence?.occlusion.notes ?? []) {
    findings.push({ kind: "gap", text: occlusionNote });
  }
  for (const limitation of intelDoc?.limitations ?? []) {
    findings.push({ kind: "note", text: limitation });
  }
  for (const reason of intelDoc?.capability_readiness.reasons ?? []) {
    findings.push({ kind: "note", text: reason });
  }
  if ((diagnostic?.duplicate_fdi_numbers?.length ?? 0) > 0) {
    findings.push({
      kind: "warning",
      text: `Duplicate FDI: ${diagnostic?.duplicate_fdi_numbers?.join(", ")}`,
    });
  }
  if ((diagnostic?.missing_fdi_numbers?.length ?? 0) > 0) {
    findings.push({
      kind: "gap",
      text: `Missing FDI: ${diagnostic?.missing_fdi_numbers?.join(", ")}`,
    });
  }
  if ((diagnostic?.excluded_fragment_count ?? 0) > 0) {
    findings.push({
      kind: "note",
      text: `Excluded zero-face fragments: ${diagnostic?.excluded_fragment_count}`,
    });
  }
  if ((diagnostic?.uncertain_teeth ?? 0) > 0) {
    findings.push({
      kind: "gap",
      text: `Uncertain teeth: ${diagnostic?.uncertain_teeth}`,
    });
  }
  if ((diagnostic?.unidentified_teeth ?? 0) > 0) {
    findings.push({
      kind: "gap",
      text: `Unidentified teeth: ${diagnostic?.unidentified_teeth}`,
    });
  }
  if (
    intelDoc?.capability_readiness.treatment_setup_readiness === "not_available" ||
    intelDoc?.capability_readiness.treatment_setup_readiness === "requires_review"
  ) {
    findings.push({
      kind: "gap",
      text: "Treatment setup is not unlocked by intelligence objects alone.",
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

export function formatTruthState(state: IntelligenceTruthState | ProductTruthState | null): string {
  if (!state) return "Not Available";
  return PRODUCT_TRUTH_LABELS[state as ProductTruthState] ?? state.replaceAll("_", " ");
}

export function formatMeshMeasurement(validation: MeshValidationResult | null): string {
  if (!validation) return "Unavailable";
  return `${validation.triangle_count.toLocaleString()} triangles`;
}

export function formatOcclusionAvailability(value: string | null): string {
  if (!value) return "Unavailable";
  return value.replaceAll("_", " ");
}
