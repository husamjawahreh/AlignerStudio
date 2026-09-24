import type { DataProvenance } from "@alignerstudio/contracts";

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
  toothA: number;
  toothB: number;
  currentDistance: number | null;
  targetDistance: number | null;
  proposedAmount: number | null;
  status: ProposalStatus;
  warning: string;
  fixture: boolean;
  stage?: number;
  amountUnit?: string;
}

export interface ReviewAttachmentSite {
  siteId: string;
  toothNumber: number;
  attachmentType: string;
  referencePoint: [number, number, number] | null;
  reason: string;
  status: ProposalStatus;
  warning: string;
  fixture: boolean;
  dimensions?: [number, number, number] | null;
  stage?: number;
  generated?: boolean;
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
  };
  validationSummary?: {
    geometry: "computed" | "unavailable";
    contacts: "computed" | "unavailable";
    proximity: "computed" | "unavailable";
    collisions: "computed" | "unavailable";
    movementConstraints: "computed" | "unavailable";
    stageConsistency: "computed" | "unavailable";
    dataCompleteness: "computed" | "warning" | "unavailable";
    doctorReview: "required" | "complete";
    findings: readonly string[];
  };
}
