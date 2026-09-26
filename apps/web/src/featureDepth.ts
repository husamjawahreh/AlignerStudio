/**
 * Wave 9 feature-depth classification.
 *
 * This is a presentation contract over existing engines. It does not create
 * movement limits, IPR prescriptions, attachment designs, or clinical axes.
 */

export type FeatureAvailability =
  | "executable"
  | "fixture_only"
  | "blocked_by_data"
  | "blocked_by_environment"
  | "review_only";

export interface FeatureDepthRow {
  id: string;
  label: string;
  availability: FeatureAvailability;
  /** Doctor-facing reason. No engine names. */
  reason: string;
}

export function classifyFeatureDepth(input: {
  liveInferenceAvailable: boolean;
  hasStoredPlan: boolean;
  fixtureSegmentation: boolean;
  movementLimitsConfigured: boolean;
  iprValueSource: "doctor_entered" | "centroid_distance" | "unavailable" | null;
  attachmentApproved: boolean;
  occlusionEvidence: boolean;
  clinicalAxesFromMeshPca: boolean;
  validationScorePresent: boolean;
}): readonly FeatureDepthRow[] {
  return [
    {
      id: "segmentation",
      label: "Segmentation review",
      availability: input.liveInferenceAvailable
        ? "executable"
        : "blocked_by_environment",
      reason: input.liveInferenceAvailable
        ? "A segmentation result can be reviewed."
        : "Clinical segmentation cannot be completed on this computer.",
    },
    {
      id: "tooth-edit",
      label: "Tooth movement",
      availability: input.hasStoredPlan ? "executable" : "blocked_by_data",
      reason: input.hasStoredPlan
        ? input.movementLimitsConfigured
          ? "Edits use the stored plan and the configured limits."
          : "Edits use the stored plan. No movement limits are configured."
        : "A stored treatment plan is required before a tooth can be moved.",
    },
    {
      id: "staging",
      label: "Staging",
      availability: input.hasStoredPlan ? "executable" : "blocked_by_data",
      reason: input.hasStoredPlan
        ? "Stages follow the stored target. They are not a clinical optimum."
        : "Staging needs a stored treatment target.",
    },
    {
      id: "ipr",
      label: "IPR",
      availability:
        input.iprValueSource === "doctor_entered"
          ? "review_only"
          : input.iprValueSource === "centroid_distance"
            ? "review_only"
            : "blocked_by_data",
      reason:
        input.iprValueSource === "centroid_distance"
          ? "A centroid distance is a geometric review value, not an IPR prescription."
          : input.iprValueSource === "doctor_entered"
            ? "The amount was entered for review. It is not an enamel prescription."
            : "No interproximal measurement is available from the current geometry.",
    },
    {
      id: "attachment",
      label: "Attachments",
      availability: input.attachmentApproved ? "review_only" : "review_only",
      reason: input.attachmentApproved
        ? "An approved attachment is not produced by this workspace."
        : "Attachment rows are review candidates. Dimensions are not invented.",
    },
    {
      id: "occlusion",
      label: "Occlusion and anatomy",
      availability: input.occlusionEvidence ? "review_only" : "blocked_by_data",
      reason: input.clinicalAxesFromMeshPca
        ? "A generic mesh direction is not a clinical axis."
        : input.occlusionEvidence
          ? "Only supplied registration evidence can be reviewed."
          : "Crown-only geometry does not establish occlusion, roots, or landmarks.",
    },
    {
      id: "validation",
      label: "Validation",
      availability: input.hasStoredPlan ? "executable" : "blocked_by_data",
      reason: input.validationScorePresent
        ? "A score is not a validation result."
        : "Findings stay findings. A missing check is not a pass.",
    },
    {
      id: "production",
      label: "Production export",
      availability: input.hasStoredPlan ? "executable" : "blocked_by_data",
      reason: "Export is an engineering package. It is not manufacturing certification.",
    },
    {
      id: "fixture-segmentation",
      label: "Test-only segmentation",
      availability: input.fixtureSegmentation ? "fixture_only" : "blocked_by_data",
      reason: "A test mesh is not patient inference.",
    },
  ];
}

export function featureById(rows: readonly FeatureDepthRow[], id: string): FeatureDepthRow {
  const row = rows.find((item) => item.id === id);
  if (!row) throw new Error(`Missing feature ${id}`);
  return row;
}
