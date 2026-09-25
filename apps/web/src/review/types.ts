import type {
  DataProvenance,
  ToothCoordinateSystemPayload,
  ToothLandmarksPayload,
} from "@alignerstudio/contracts";

export type ReviewArch = "upper" | "lower";
export type ValidationStatus = "pass" | "warning" | "error" | "unavailable";
export type ReviewProposalKind = "original_generated" | "doctor_edited" | "recalculated";
export type ProposalStatus =
  | "generated"
  | "doctor_modified"
  | "accepted"
  | "rejected"
  | "needs_review"
  | "unable_to_determine";

export interface MovementSummary {
  translationX: number;
  translationY: number;
  translationZ: number;
  rotation: number;
  tip: number;
  torque: number;
  angulation: number;
  intrusion: number;
  extrusion: number;
  locked?: boolean;
  excluded?: boolean;
}

export interface ReviewToothMesh {
  instanceId: number;
  fdiNumber: number | null;
  toothRef?: string | null;
  semanticLabel?: number | null;
  planningMode?: "clinical_fdi" | "semantic_only_experimental";
  arch: ReviewArch;
  confidence: number;
  vertices: readonly [number, number, number][];
  faces: readonly [number, number, number][];
  centroid?: readonly [number, number, number];
  landmarks?: ToothLandmarksPayload | null;
  coordinateSystem?: ToothCoordinateSystemPayload | null;
  movementReferenceFrame?: ToothCoordinateSystemPayload | null;
  anatomyExtent?: "crown_only_stl" | "root_bone_cbct";
  identificationStatus?: string;
  movement: MovementSummary;
  rate?: MovementSummary;
  accumulated?: MovementSummary;
  limitStatus?: "not_configured" | "within_configured_limit" | "exceeded";
  validationStatus: ValidationStatus;
  validationMessage: string;
  provenance: DataProvenance;
  fixture: boolean;
  experimental?: boolean;
}

export interface ReviewStage {
  index: number;
  stageId: string;
  teeth: readonly ReviewToothMesh[];
  validationStatus: ValidationStatus;
  collisionCount: number;
  proximityCount: number;
  contactCount: number;
  warnings: readonly string[];
  provenance: DataProvenance;
  fixture: boolean;
  label?: string;
  type?: "initial" | "intermediate" | "macro" | "micro" | "final";
  validationFindings?: readonly string[];
  metadata?: Readonly<Record<string, string>>;
}

export type EditProvenanceReason =
  | "doctor_edit"
  | "doctor_reset"
  | "gizmo_edit"
  | "numeric_edit"
  | "reset"
  | "system_restore";

export interface ReviewEditRecord {
  editId: string;
  toothNumber: number | string;
  previousMovement: MovementSummary;
  newMovement: MovementSummary;
  timestamp: string;
  versionId: string;
  provenance: DataProvenance;
  reason: EditProvenanceReason;
  source?: "doctor";
}

export interface ReviewIPRSite {
  siteId: string;
  toothA: number | string;
  toothB: number | string;
  toothRefA?: string | null;
  toothRefB?: string | null;
  currentDistance: number | null;
  targetDistance: number | null;
  measuredAmount?: number | null;
  computedProposalAmount?: number | null;
  doctorEnteredAmount?: number | null;
  proposedAmount: number | null;
  status: ProposalStatus;
  warning: string;
  fixture: boolean;
  stage?: number | null;
  amountUnit?: string;
  measurementMethod?: string;
  valueSource?: "measured" | "computed_proposal" | "doctor_entered" | "not_available";
  truthState?: "verified" | "computed" | "requires_review" | "not_available";
  clinicallyApproved?: false;
  limitations?: readonly string[];
}

export interface ReviewAttachmentSite {
  siteId: string;
  toothNumber: number | string;
  toothRef?: string | null;
  attachmentType: string;
  referencePoint: [number, number, number] | null;
  reason: string;
  status: ProposalStatus;
  warning: string;
  fixture: boolean;
  dimensions?: [number, number, number] | null;
  stage?: number | null;
  generated?: boolean;
  truthState?: "verified" | "computed" | "requires_review" | "not_available";
  geometryAvailable?: boolean;
  clinicallyApproved?: false;
  limitations?: readonly string[];
}

export type CapabilityStatus = "computed" | "unavailable" | "warning" | "boundary_only";

export interface ManufacturingBoundary {
  packageKind: string;
  artifactLayers: readonly string[];
  stageModelExport: CapabilityStatus;
  applianceShellGeneration: CapabilityStatus;
  trimlineCutline: CapabilityStatus;
  shellThicknessMaterialProfile: CapabilityStatus;
  undercutEngagementChecks: CapabilityStatus;
  printableModelPreparation: CapabilityStatus;
  manufacturingQcReport: CapabilityStatus;
  treatmentVsManufacturingSeparated: boolean;
  notes: readonly string[];
}

export interface ReviewBundle {
  stages: readonly ReviewStage[];
  provenance: DataProvenance;
  fixture: boolean;
  realDataAvailable: boolean;
  unavailableReason?: string;
  proposalKind: ReviewProposalKind;
  editHistory: readonly ReviewEditRecord[];
  iprSites: readonly ReviewIPRSite[];
  attachmentSites: readonly ReviewAttachmentSite[];
  sourceKind?: string;
  experimental?: boolean;
  planningMode?: "clinical_fdi" | "semantic_only_experimental";
  planSummary?: {
    movedToothCount: number;
    totalMovement: number;
    notableConflicts: readonly string[];
    dataGaps: readonly string[];
    warnings: readonly string[];
    source: "deterministic planner" | "experimental model" | "doctor edit";
    doctorReviewRequired: boolean;
    alternativeCount?: number;
    activeAlternativeStrategy?: string | null;
  };
  validationSummary?: {
    geometry: CapabilityStatus;
    contacts: CapabilityStatus;
    proximity: CapabilityStatus;
    collisions: CapabilityStatus;
    movementConstraints: CapabilityStatus;
    stageConsistency: CapabilityStatus;
    dataCompleteness: CapabilityStatus;
    provenance: CapabilityStatus;
    doctorReview: "required" | "complete";
    findings: readonly string[];
  };
  manufacturingBoundary?: ManufacturingBoundary;
  planningIntelligence?: PlanningIntelligence;
  /** WP-05 Treatment Setup 2.0 — stable lineage + content hashes. */
  planId?: string;
  versionId?: string;
  parentVersionId?: string | null;
  setupPlanId?: string;
  treatmentSetup?: TreatmentSetup2Payload;
  smartStaging?: SmartStagingPayload;
  /** WP-07 clinical tools honesty / readiness contract. */
  clinicalTools?: ClinicalToolsPayload;
  stagingId?: string;
}

export type ReadinessState =
  | "available"
  | "requires_review"
  | "not_available"
  | "unavailable";

export interface TreatmentSetupVersionMeta {
  version_id: string;
  parent_version_id: string | null;
  plan_id: string;
  setup_plan_id: string;
  created_at: string;
  author_source: string;
  description: string;
  proposal_kind: string;
  moved_tooth_count: number;
  validation_status: string | null;
  change_summary: string;
  immutable: boolean;
  clinically_approved: false;
}

export interface TreatmentSetupReadiness {
  real_geometry: ReadinessState;
  identity: ReadinessState;
  arch: ReadinessState;
  transform: ReadinessState;
  constraint: ReadinessState;
  validation: ReadinessState;
  occlusion: ReadinessState;
  clinical_axes: ReadinessState;
  notes: readonly string[];
  unsupported_features_unlocked: false;
  clinically_approved: false;
}

export interface TreatmentSetupToothDelta {
  tooth_key: string;
  tooth_ref: string | null;
  arch: string | null;
  translation_delta: readonly [number, number, number];
  rotation_delta: readonly [number, number, number];
  changed: boolean;
  terminology: "geometric";
}

export interface TreatmentSetupComparison {
  left_version_id: string;
  right_version_id: string;
  changed_teeth: readonly TreatmentSetupToothDelta[];
  changed_count: number;
  unchanged_count: number;
  left_validation_status: string | null;
  right_validation_status: string | null;
  notes: readonly string[];
  clinical_ranking: null;
  clinically_approved: false;
}

export interface TreatmentSetup2Payload {
  contract_version: "treatment_setup_2.0";
  setup_plan_id: string;
  plan_id: string;
  version_id: string;
  parent_version_id: string | null;
  proposal_kind: string;
  layers: {
    source: string;
    current: string;
    target: string;
  };
  teeth: readonly Record<string, unknown>[];
  moved_tooth_count: number;
  readiness: TreatmentSetupReadiness;
  constraint_availability: string;
  current_vs_target: TreatmentSetupComparison;
  versions: readonly TreatmentSetupVersionMeta[];
  clinically_approved: false;
  notes: readonly string[];
}

export type StagingFreshness = "current" | "stale" | "unavailable";

export type ClinicalToolTruthState =
  | "verified"
  | "computed"
  | "requires_review"
  | "not_available";

export type ClinicalToolFreshness = "current" | "stale" | "unavailable";

export interface ClinicalToolsReadiness {
  ipr_measurement: ReadinessState;
  ipr_proposal: ReadinessState;
  attachment_placement: ReadinessState;
  attachment_geometry: ReadinessState;
  validation: ReadinessState;
  setup_binding: ClinicalToolFreshness;
  staging_binding: ClinicalToolFreshness;
  doctor_review_required: boolean;
  source_geometry: ReadinessState;
  notes: readonly string[];
  clinically_approved: false;
}

export interface ClinicalToolsPayload {
  contract_version: "clinical_tools_1.0";
  source_setup_version_id: string;
  source_staging_version_id: string | null;
  adjuncts_proposal_id: string;
  freshness: ClinicalToolFreshness;
  readiness: ClinicalToolsReadiness;
  ipr_site_count: number;
  attachment_site_count: number;
  measurable_ipr_pairs: number;
  unavailable_ipr_pairs: number;
  limitations: readonly string[];
  clinically_approved: false;
  notes: readonly string[];
}

export interface SmartStagingPayload {
  contract_version: "smart_staging_1.0";
  meta?: {
    staging_plan_id: string;
    staging_version_id: string;
    parent_staging_version_id: string | null;
    source_setup_version_id: string;
    algorithm_name: string;
    algorithm_version: string;
    stage_count: number;
    affected_tooth_count: number;
    truth_state: string;
    freshness: StagingFreshness;
    limitations: readonly string[];
    clinically_approved: false;
    clinically_optimal: false;
  };
  staging_id?: string;
  stage_count?: number;
  final_equals_target?: boolean;
  reconstruction_max_error?: number;
  technical_numerical_tolerance?: number;
  readiness?: Record<string, unknown>;
  freshness?: StagingFreshness;
  versions?: readonly Record<string, unknown>[];
  clinically_approved: false;
  clinically_optimal: false;
  notes: readonly string[];
  limitations?: readonly string[];
}

export interface ModelOutputContract {
  modelName: string;
  modelVersion: string;
  inputProvenance: string;
  confidence: number | null;
  uncertainty: number | null;
  limitations: readonly string[];
  deterministicValidationStatus: string;
  deterministicValidationFindings: readonly string[];
  decisionState: string;
}

export interface SetupAlternative {
  alternativeId: string;
  strategy: string;
  label: string;
  contract: ModelOutputContract;
  collisionCount: number;
  proximityCount: number;
  contactCount: number;
  stageCount: number;
  isActive: boolean;
}

export interface ResearchAdapterEvaluation {
  adapterId: string;
  modelName: string;
  productProblem: string;
  decision: string;
  status: string;
  modelVersion: string | null;
  provenanceNotes: string;
  benchmarkStatus: string;
  limitations: readonly string[];
  comparedToDeterministicValidation: string;
}

export interface PlanningIntelligence {
  landmarkAssistedTargetSetup: CapabilityStatus;
  archFormAwarePlanning: CapabilityStatus;
  occlusionAwarePlanning: CapabilityStatus;
  collisionAwareCandidateGeneration: CapabilityStatus;
  constrainedSixDofTrajectories: CapabilityStatus;
  stagingProposals: CapabilityStatus;
  alternativeSetups: CapabilityStatus;
  alternatives: readonly SetupAlternative[];
  researchAdapters: readonly ResearchAdapterEvaluation[];
  notes: readonly string[];
  doctorDecisionRequired: boolean;
  rule: string;
}
