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

export interface ReviewEditRecord {
  editId: string;
  toothNumber: number | string;
  previousMovement: MovementSummary;
  newMovement: MovementSummary;
  timestamp: string;
  versionId: string;
  provenance: DataProvenance;
  reason: "doctor_edit" | "doctor_reset";
  source?: "doctor";
}

export interface ReviewIPRSite {
  siteId: string;
  toothA: number | string;
  toothB: number | string;
  currentDistance: number | null;
  targetDistance: number | null;
  proposedAmount: number | null;
  status: ProposalStatus;
  warning: string;
  fixture: boolean;
  stage?: number | null;
  amountUnit?: string;
}

export interface ReviewAttachmentSite {
  siteId: string;
  toothNumber: number | string;
  attachmentType: string;
  referencePoint: [number, number, number] | null;
  reason: string;
  status: ProposalStatus;
  warning: string;
  fixture: boolean;
  dimensions?: [number, number, number] | null;
  stage?: number | null;
  generated?: boolean;
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
