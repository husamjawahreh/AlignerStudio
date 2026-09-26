/**
 * Wave 3 clinical interaction model.
 *
 * Pure presentation and navigation decisions. This module does not create
 * segmentation, FDI numbers, axes, roots, occlusion, or gingiva anatomy.
 * Geometric validation and treatment undo stay in their existing engines.
 */

import type { PipelineDiagnostic } from "../api/client";
import type { ToothLabelMode } from "../viewer/presentation/labelPolicy";
import type { WorkflowStepId } from "../workflow";

export type { ToothLabelMode };

export type FeedbackState =
  | "processing"
  | "completed"
  | "failed"
  | "blocked_by_environment"
  | "cancelled"
  | "interrupted"
  | "stale"
  | "requires_review"
  | "not_available";

export type SegmentationEvidenceKind =
  | "not_run"
  | "blocked_by_environment"
  | "failed"
  | "not_available"
  | "fixture_test_only"
  | "real_model_inference"
  | "requires_review";

export interface ToothIdentityInput {
  instanceId: number;
  fdiNumber?: number | null;
  toothRef?: string | null;
  arch?: "upper" | "lower" | string | null;
  planningMode?: "clinical_fdi" | "semantic_only_experimental" | string | null;
  identificationStatus?: string | null;
  provenance?: string | null;
  fixture?: boolean;
  experimental?: boolean;
  confidence?: number | null;
}

export interface ToothReviewLabel {
  /** Semantic key used for selection. Never a mesh index. */
  toothRef: string;
  /** Doctor-facing primary label. FDI only when authoritative. */
  text: string;
  unresolved: boolean;
  fdiAuthoritative: boolean;
  arch: "upper" | "lower" | null;
}

export interface SegmentationReviewModel {
  kind: SegmentationEvidenceKind;
  headline: string;
  whatHappened: string;
  nextStep: string;
  unavailable: string;
  retrySafe: boolean;
  countsAvailable: boolean;
  instanceCountLabel: string;
  upperCountLabel: string;
  lowerCountLabel: string;
  unresolvedIdentityLabel: string;
  /** Shown only when a real-model confidence value exists. */
  confidenceLabel: string | null;
  provenanceLabel: string;
  runtimeBlocker: string | null;
  /** Always this phrase. Absence of a crown is not a missing-tooth diagnosis. */
  missingToothStatement: "Identity/data not established";
  advanced: readonly { label: string; value: string }[];
}

export interface FeedbackModel {
  state: FeedbackState;
  whatHappened: string;
  next: string;
  unavailable: string;
  retrySafe: boolean;
  provenance: string | null;
  elapsedLabel: string | null;
  /** Always null. Remaining time is never invented. */
  remainingEstimate: null;
  remainingNote: "No reliable remaining-time estimate.";
}

export type CameraCommand =
  | { type: "fit-case" }
  | { type: "fit-arch"; arch: "upper" | "lower" }
  | { type: "fit-selection"; keys: readonly string[] }
  | { type: "preset"; preset: "occlusal" | "front" | "right" }
  | { type: "reset" };

export type WorkspaceShortcut =
  | "clear"
  | "fit-selection"
  | "fit-case"
  | "arch-upper"
  | "arch-lower"
  | "arch-both"
  | "undo"
  | "redo"
  | "delete";

export interface ToolItem {
  id: string;
  label: string;
  available: boolean;
  reason: string;
  shortcut?: string;
  active?: boolean;
}

export interface UnavailableToolNote {
  id: string;
  label: string;
  reason: string;
}

export interface InspectorRow {
  label: string;
  value: string;
}

export interface InspectorModel {
  mode: "minimized" | "case" | "tooth" | "group" | "blocked";
  title: string;
  rows: InspectorRow[];
  limitations: string[];
  advanced: InspectorRow[];
}

export interface LayoutBudget {
  header: number;
  rail: number;
  inspector: number;
  viewport: number;
  viewportDominant: boolean;
  pageScroll: false;
}

const CLINICAL_UNDO = new Set<WorkspaceShortcut>(["undo", "redo"]);

export function shortcutChangesClinicalState(id: WorkspaceShortcut): boolean {
  return CLINICAL_UNDO.has(id);
}

export function isTextEntryTarget(target: EventTarget | null): boolean {
  if (typeof HTMLElement === "undefined") return false;
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return Boolean(target.isContentEditable);
}

export function matchWorkspaceShortcut(event: {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  shiftKey: boolean;
  altKey: boolean;
}): WorkspaceShortcut | null {
  if (event.altKey) return null;
  const mod = event.metaKey || event.ctrlKey;
  const key = event.key;
  if (mod && event.shiftKey && (key === "z" || key === "Z")) return "redo";
  if (mod && !event.shiftKey && (key === "z" || key === "Z")) return "undo";
  if (mod) return null;
  if (key === "Escape") return "clear";
  if (key === "f" || key === "F") return "fit-selection";
  if (key === "Home") return "fit-case";
  if (key === "1") return "arch-upper";
  if (key === "2") return "arch-lower";
  if (key === "0") return "arch-both";
  if (key === "Delete" || key === "Backspace") return "delete";
  return null;
}

/** Delete never removes persisted clinical data. There is no reversible delete tool. */
export function deleteShortcutEffect(): { apply: false; reason: string } {
  return {
    apply: false,
    reason:
      "Delete does not remove clinical tooth data. No reversible delete action is available.",
  };
}

export function reviewToothRef(tooth: ToothIdentityInput): string {
  if (tooth.toothRef) return tooth.toothRef;
  return `instance:${tooth.instanceId}`;
}

/**
 * FDI is shown only when the persisted tooth says clinical_fdi, the number
 * is present, identity is resolved, and the record is not fixture/experimental.
 */
export function fdiIsAuthoritative(tooth: ToothIdentityInput): boolean {
  if (tooth.fdiNumber == null || !Number.isFinite(tooth.fdiNumber)) return false;
  if (tooth.fixture || tooth.experimental) return false;
  if (tooth.provenance === "fixture" || tooth.provenance === "experimental") return false;
  if (tooth.planningMode !== "clinical_fdi") return false;
  const status = (tooth.identificationStatus ?? "").trim().toLowerCase();
  return status === "identified" || status === "resolved" || status === "verified";
}

export function toothReviewLabel(tooth: ToothIdentityInput): ToothReviewLabel {
  const toothRef = reviewToothRef(tooth);
  const fdiAuthoritative = fdiIsAuthoritative(tooth);
  const arch = tooth.arch === "upper" || tooth.arch === "lower" ? tooth.arch : null;
  return {
    toothRef,
    text: fdiAuthoritative ? `FDI ${tooth.fdiNumber}` : toothRef,
    unresolved: !fdiAuthoritative,
    fdiAuthoritative,
    arch,
  };
}

function countLabel(available: boolean, count: number): string {
  return available ? String(count) : "Not available";
}

export function buildSegmentationReviewModel(input: {
  diagnostic: PipelineDiagnostic | null;
  teeth: readonly ToothIdentityInput[];
  patientReference?: string | null;
}): SegmentationReviewModel {
  const diagnostic = input.diagnostic;
  const teeth = input.teeth;
  const state = diagnostic?.state ?? null;
  const truth = diagnostic?.segmentation_truth_state ?? null;
  const blocked = state === "blocked_by_environment" || truth === "blocked_by_environment";
  const failed = state === "segmentation_failed" || truth === "failed";
  const unavailable =
    !diagnostic || state === "model_unavailable" || truth === "not_available";
  const fixture =
    Boolean(diagnostic?.fixture) ||
    diagnostic?.provenance === "fixture" ||
    teeth.some((tooth) => tooth.fixture || tooth.provenance === "fixture");
  const real =
    !fixture &&
    !blocked &&
    !failed &&
    diagnostic?.provenance === "real" &&
    teeth.length > 0;

  let kind: SegmentationEvidenceKind = "not_run";
  if (!diagnostic) kind = "not_run";
  else if (blocked) kind = "blocked_by_environment";
  else if (failed) kind = "failed";
  else if (state === "model_unavailable" || truth === "not_available") kind = "not_available";
  else if (fixture) kind = "fixture_test_only";
  else if (real) kind = "real_model_inference";
  else if (teeth.length > 0) kind = "requires_review";
  else if (unavailable) kind = "not_available";
  else kind = "requires_review";

  const countsAvailable =
    kind === "real_model_inference" ||
    kind === "fixture_test_only" ||
    kind === "requires_review";
  const upper = teeth.filter((tooth) => tooth.arch === "upper").length;
  const lower = teeth.filter((tooth) => tooth.arch === "lower").length;
  const unresolved = teeth.filter((tooth) => !fdiIsAuthoritative(tooth)).length;
  const confidence =
    kind === "real_model_inference" &&
    typeof diagnostic?.identification_confidence === "number" &&
    Number.isFinite(diagnostic.identification_confidence)
      ? diagnostic.identification_confidence
      : null;

  const blocker = diagnostic?.runtime_blocker?.trim() || null;
  const headlines: Record<SegmentationEvidenceKind, string> = {
    not_run: "Segmentation not run",
    blocked_by_environment: "Blocked by environment",
    failed: "Segmentation failed",
    not_available: "Segmentation not available",
    fixture_test_only: "Fixture / test-only",
    real_model_inference: "Real-model inference",
    requires_review: "Requires review",
  };

  const what: Record<SegmentationEvidenceKind, string> = {
    not_run: "No segmentation result is stored for this case.",
    blocked_by_environment: blocker
      ? blocker
      : "Live ToothInstanceNet inference did not run. The host runtime is blocked. Fixture teeth were not substituted.",
    failed: diagnostic?.failures?.[0] ?? "Segmentation failed. No tooth instances were accepted.",
    not_available:
      diagnostic?.failures?.[0] ??
      "The segmentation model result is not available. This is not a successful count of zero teeth.",
    fixture_test_only:
      "This output is fixture or test-only. It is not live ToothInstanceNet inference and it is not clinical evidence.",
    real_model_inference:
      "Tooth instances come from persisted real-model inference. Clinical FDI is shown only where that evidence resolved it.",
    requires_review:
      "Tooth instances are present, but identity is not an authoritative clinical FDI assignment.",
  };

  const next: Record<SegmentationEvidenceKind, string> = {
    not_run: "Import both arches, then run segmentation review.",
    blocked_by_environment:
      "Retry with a new job only after the reported runtime blocker is resolved. There is no mid-stage resume.",
    failed: "Start a new segmentation job after correcting the scan or runtime failure.",
    not_available: "Review the scan import, then retry segmentation. Do not treat an empty result as zero teeth.",
    fixture_test_only: "Use this only to inspect test geometry. Do not approve it as a clinical segmentation.",
    real_model_inference: "Select a tooth to review identity, arch, and confidence.",
    requires_review: "Review each tooth_ref. Do not assign FDI numbers that the model did not resolve.",
  };

  const retrySafe = kind === "blocked_by_environment" || kind === "failed" || kind === "not_available" || kind === "not_run";

  return {
    kind,
    headline: headlines[kind],
    whatHappened: what[kind],
    nextStep: next[kind],
    unavailable:
      kind === "real_model_inference"
        ? "Clinical axes, roots, occlusion, and missing-tooth conclusions remain unavailable unless a later authoritative result says otherwise."
        : "Tooth-level clinical review controls are unavailable until a real segmentation result exists.",
    retrySafe,
    countsAvailable,
    instanceCountLabel: countLabel(countsAvailable, teeth.length),
    upperCountLabel: countLabel(countsAvailable, upper),
    lowerCountLabel: countLabel(countsAvailable, lower),
    unresolvedIdentityLabel: countsAvailable
      ? `${unresolved} unresolved`
      : "Not available",
    confidenceLabel: confidence === null ? null : confidence.toFixed(3),
    provenanceLabel:
      kind === "real_model_inference"
        ? "Real-model inference"
        : kind === "fixture_test_only"
          ? "Fixture / test-only"
          : kind === "blocked_by_environment"
            ? "Blocked by environment"
            : kind === "failed"
              ? "Failed"
              : kind === "not_run"
                ? "Not run"
                : "Not available",
    runtimeBlocker: kind === "blocked_by_environment" ? blocker : null,
    missingToothStatement: "Identity/data not established",
    advanced: [
      { label: "Patient", value: input.patientReference?.trim() || "Not set" },
      { label: "Pipeline state", value: state ?? "Not run" },
      { label: "Truth state", value: truth ?? "Not reported" },
      { label: "Backend", value: diagnostic?.backend ?? "Not reported" },
      { label: "Provenance", value: diagnostic?.provenance ?? "Not reported" },
      {
        label: "Source hash",
        value: diagnostic?.preprocessing?.source_mesh_sha256 ?? "Not reported",
      },
    ],
  };
}

export function buildDentalMapEntries(teeth: readonly ToothIdentityInput[]): ToothReviewLabel[] {
  return teeth.map((tooth) => toothReviewLabel(tooth));
}

export function buildFeedbackModel(input: {
  stageStatus?: string | null;
  userMessage?: string | null;
  elapsedSeconds?: number | null;
  errorCode?: string | null;
  segmentation?: SegmentationReviewModel | null;
}): FeedbackModel {
  const status = (input.stageStatus ?? "").toUpperCase();
  const interrupted =
    status === "INTERRUPTED" || (input.errorCode ?? "").toLowerCase().includes("interrupt");
  let state: FeedbackState = "not_available";
  if (status === "PROCESSING") state = "processing";
  else if (interrupted) state = "interrupted";
  else if (status === "CANCELLED") state = "cancelled";
  else if (status === "FAILED") state = "failed";
  else if (status === "STALE") state = "stale";
  else if (status === "COMPLETED") state = "completed";
  else if (input.segmentation?.kind === "blocked_by_environment") state = "blocked_by_environment";
  else if (input.segmentation?.kind === "failed") state = "failed";
  else if (input.segmentation?.kind === "fixture_test_only") state = "requires_review";
  else if (input.segmentation?.kind === "real_model_inference") state = "requires_review";
  else if (input.segmentation?.kind === "requires_review") state = "requires_review";
  else state = "not_available";

  const elapsed =
    typeof input.elapsedSeconds === "number" && Number.isFinite(input.elapsedSeconds)
      ? `Elapsed ${formatElapsed(input.elapsedSeconds)}`
      : null;

  const fromSegmentation = input.segmentation;
  const what =
    input.userMessage?.trim() ||
    fromSegmentation?.whatHappened ||
    (state === "processing"
      ? "Working. Remaining time is not estimated."
      : "No clinical result is ready.");

  return {
    state,
    whatHappened: what,
    next: fromSegmentation?.nextStep ?? "Continue when the current step has a truthful result.",
    unavailable: fromSegmentation?.unavailable ?? "Downstream clinical review is not available yet.",
    retrySafe: state === "failed" || state === "blocked_by_environment" || state === "cancelled" || state === "interrupted" || state === "stale",
    provenance: fromSegmentation?.provenanceLabel ?? null,
    elapsedLabel: state === "processing" ? elapsed : elapsed,
    remainingEstimate: null,
    remainingNote: "No reliable remaining-time estimate.",
  };
}

function formatElapsed(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

export interface ToolbarContext {
  workspace: WorkflowStepId;
  sceneAvailable: boolean;
  segmentationKind: SegmentationEvidenceKind;
  selectionCount: number;
  archMode: "upper" | "lower" | "both";
  isolateActive: boolean;
  labelMode: ToothLabelMode;
  gingivaVisible: boolean;
  segmentationVisible: boolean;
  wireframe: boolean;
  movementVisible: boolean;
  targetVisible: boolean;
  treatmentAvailable: boolean;
  validationAvailable: boolean;
  canTransform: boolean;
}

export function buildContextualTools(ctx: ToolbarContext): {
  tools: ToolItem[];
  unavailable: UnavailableToolNote[];
} {
  const reviewBlocked =
    ctx.segmentationKind === "blocked_by_environment" ||
    ctx.segmentationKind === "failed" ||
    ctx.segmentationKind === "not_available" ||
    ctx.segmentationKind === "not_run";
  const tools: ToolItem[] = [];
  const unavailable: UnavailableToolNote[] = [];

  const view = (tool: ToolItem) => {
    tools.push(tool);
  };

  if (ctx.sceneAvailable) {
    view({
      id: "fit-case",
      label: "Fit case",
      available: true,
      reason: "Frame the full case.",
      shortcut: "Home",
      active: false,
    });
    view({
      id: "fit-arch",
      label: "Fit arch",
      available: ctx.archMode !== "both" || ctx.sceneAvailable,
      reason: "Frame the active arch filter.",
      active: false,
    });
    view({
      id: "view-occlusal",
      label: "Occlusal",
      available: true,
      reason: "Standard occlusal view.",
    });
    view({
      id: "view-front",
      label: "Front",
      available: true,
      reason: "Standard frontal view.",
    });
    view({
      id: "view-lateral",
      label: "Lateral",
      available: true,
      reason: "Standard right lateral view.",
    });
    view({
      id: "reset-view",
      label: "Reset view",
      available: true,
      reason: "Fit the case. Ordinary selection does not move the camera.",
    });
    view({
      id: "arch-upper",
      label: "Upper",
      available: true,
      reason: "Show the upper arch.",
      shortcut: "1",
      active: ctx.archMode === "upper",
    });
    view({
      id: "arch-lower",
      label: "Lower",
      available: true,
      reason: "Show the lower arch.",
      shortcut: "2",
      active: ctx.archMode === "lower",
    });
    view({
      id: "arch-both",
      label: "Both",
      available: true,
      reason: "Show both arches.",
      shortcut: "0",
      active: ctx.archMode === "both",
    });
    view({
      id: "labels",
      label:
        ctx.labelMode === "off"
          ? "Labels off"
          : ctx.labelMode === "selected"
            ? "Labels: selected"
            : ctx.labelMode === "arch"
              ? "Labels: arch"
              : "Labels: all",
      available: true,
      reason: "Cycle label density: selected, arch, all, off. tooth_ref unless FDI is authoritative.",
      active: ctx.labelMode !== "off",
    });
    view({
      id: "gingiva",
      label: "Gingiva",
      available: true,
      reason: "Presentation-only gingiva. It is not clinical anatomy and does not enter calculations.",
      active: ctx.gingivaVisible,
    });
    view({
      id: "segmentation",
      label: "Teeth",
      available: true,
      reason: "Show or hide segmented tooth surfaces.",
      active: ctx.segmentationVisible,
    });
    view({
      id: "wireframe",
      label: "Wireframe",
      available: true,
      reason: "Presentation wireframe. It does not change clinical geometry.",
      active: ctx.wireframe,
    });
  }

  if (ctx.selectionCount === 1 && !reviewBlocked) {
    view({
      id: "fit-selection",
      label: "Fit selection",
      available: true,
      reason: "Frame the selected tooth_ref.",
      shortcut: "F",
    });
    view({
      id: "isolate",
      label: "Isolate",
      available: true,
      reason: "Show only the selected tooth.",
      active: ctx.isolateActive,
    });
  } else if (ctx.selectionCount > 1 && !reviewBlocked) {
    view({
      id: "fit-selection",
      label: "Fit selection",
      available: true,
      reason: "Frame the selected tooth set.",
      shortcut: "F",
    });
  }

  if (ctx.treatmentAvailable && (ctx.workspace === "treatment-setup" || ctx.workspace === "staging" || ctx.workspace === "refinement")) {
    view({
      id: "target",
      label: "Target",
      available: true,
      reason: "Show the stored treatment target beside current geometry. This does not approve the plan.",
      active: ctx.targetVisible,
    });
    view({
      id: "movement",
      label: "Movement",
      available: true,
      reason: "Show or hide remaining-movement lines.",
      active: ctx.movementVisible,
    });
  } else if (!ctx.treatmentAvailable) {
    unavailable.push({
      id: "target",
      label: "Current / target",
      reason: "No treatment target is stored for this case.",
    });
  }

  if (ctx.workspace === "validation" && !ctx.validationAvailable) {
    unavailable.push({
      id: "validation-overlay",
      label: "Validation overlay",
      reason: "Validation findings are not available yet.",
    });
  }

  if (!ctx.canTransform || ctx.workspace !== "refinement") {
    unavailable.push({
      id: "move",
      label: "Move / transform",
      reason:
        ctx.workspace === "refinement"
          ? "Transform is unavailable for the current selection."
          : "Move is available in Refinement when a transformable tooth is selected.",
    });
  }

  unavailable.push({
    id: "measure",
    label: "Measure",
    reason: "No measurement tool is active. Distances are not invented.",
  });

  if (reviewBlocked && ctx.workspace === "analysis") {
    unavailable.push({
      id: "segmentation-review-tools",
      label: "Segmentation correction",
      reason: "Boundary edit, split, merge, and identity correction stay unavailable until a real segmentation result exists.",
    });
  }

  return { tools, unavailable };
}

export function buildInspectorModel(input: {
  minimized: boolean;
  patientReference: string | null;
  caseId: string | null;
  segmentation: SegmentationReviewModel;
  selected: ToothReviewLabel | null;
  selectionCount: number;
  confidence: number | null;
  treatmentAvailable: boolean;
}): InspectorModel {
  if (input.minimized) {
    return {
      mode: "minimized",
      title: "Inspector",
      rows: [],
      limitations: [],
      advanced: [],
    };
  }
  if (input.segmentation.kind === "blocked_by_environment" && input.selectionCount === 0) {
    return {
      mode: "blocked",
      title: "Segmentation blocked",
      rows: [
        { label: "State", value: input.segmentation.headline },
        { label: "Blocker", value: input.segmentation.runtimeBlocker ?? input.segmentation.whatHappened },
        { label: "Retry", value: input.segmentation.retrySafe ? "Safe as a new job" : "Not offered" },
        { label: "Instances", value: input.segmentation.instanceCountLabel },
      ],
      limitations: [
        input.segmentation.unavailable,
        "Clinical review controls are not shown as completed.",
        input.segmentation.missingToothStatement,
      ],
      advanced: [...input.segmentation.advanced],
    };
  }
  if (input.selectionCount > 1) {
    return {
      mode: "group",
      title: `${input.selectionCount} teeth selected`,
      rows: [
        { label: "Selection", value: "Semantic tooth_ref set" },
        { label: "Segmentation", value: input.segmentation.headline },
      ],
      limitations: ["Group edits are not a clinical numbering action."],
      advanced: [...input.segmentation.advanced],
    };
  }
  if (input.selected) {
    return {
      mode: "tooth",
      title: input.selected.text,
      rows: [
        { label: "tooth_ref", value: input.selected.toothRef },
        {
          label: "FDI",
          value: input.selected.fdiAuthoritative ? input.selected.text : "Not resolved",
        },
        { label: "Arch", value: input.selected.arch ?? "Not available" },
        { label: "Identity", value: input.selected.unresolved ? "Unresolved" : "Authoritative FDI" },
        { label: "Segmentation", value: input.segmentation.provenanceLabel },
        {
          label: "Confidence",
          value: input.confidence == null ? "Not available" : input.confidence.toFixed(3),
        },
        {
          label: "Target",
          value: input.treatmentAvailable ? "Treatment target can be compared" : "No treatment target",
        },
      ],
      limitations: [
        input.selected.unresolved ? "Identity/data not established. No FDI number was invented." : "Confirm FDI before clinical use.",
        "Clinical axes, roots, and occlusion are not shown unless an authoritative result provides them.",
        "Synthetic gingiva is presentation-only.",
      ],
      advanced: [...input.segmentation.advanced],
    };
  }
  return {
    mode: "case",
    title: input.caseId ? "Case" : "No case",
    rows: [
      { label: "Patient", value: input.patientReference?.trim() || "Not set" },
      { label: "Case", value: input.caseId ?? "Not created" },
      { label: "Segmentation", value: input.segmentation.headline },
      { label: "Provenance", value: input.segmentation.provenanceLabel },
      { label: "Next", value: input.segmentation.nextStep },
    ],
    limitations: [input.segmentation.unavailable, input.segmentation.missingToothStatement],
    advanced: [...input.segmentation.advanced],
  };
}

export function workflowBlockReason(
  step: WorkflowStepId,
  input: {
    hasCase: boolean;
    bothArchesValid: boolean;
    hasSegmentation: boolean;
    segmentationKind: SegmentationEvidenceKind;
    hasTreatment: boolean;
  },
): string | null {
  if (step === "case-intake") return null;
  if (!input.hasCase) return "Create a case first.";
  if (step === "analysis" && !input.bothArchesValid) {
    return "Import valid upper and lower scans before segmentation review.";
  }
  if (step === "treatment-setup" && !input.bothArchesValid) {
    return "Import valid upper and lower scans before treatment setup.";
  }
  if (step === "treatment-setup" && !input.hasSegmentation) {
    return input.segmentationKind === "blocked_by_environment"
      ? "Segmentation is blocked by environment. Treatment setup can open on the imported scans, but tooth instances are not available."
      : "Segmentation review has not produced tooth instances. Tooth-level setup is unavailable.";
  }
  if ((step === "staging" || step === "refinement" || step === "validation" || step === "production") && !input.hasTreatment) {
    return "A treatment plan is required before this step.";
  }
  return null;
}

export interface HeaderNextAction {
  id: "create-plan" | "open-plan" | "open-staging" | "review-findings" | "export";
  label: string;
  reason: string;
}

/** Header action only when it is not already the current step's primary button. */
export function headerNextAction(input: {
  workspace: WorkflowStepId;
  hasCase: boolean;
  bothArchesValid: boolean;
  hasSegmentation: boolean;
  hasTreatment: boolean;
  isBusy: boolean;
}): HeaderNextAction | null {
  if (!input.hasCase || input.isBusy) return null;
  if (input.workspace === "analysis" && input.bothArchesValid && !input.hasTreatment) {
    return {
      id: "create-plan",
      label: "Create Treatment Plan",
      reason: "Creates the treatment plan. This is not segmentation review.",
    };
  }
  if (input.workspace === "analysis" && input.hasTreatment) {
    return {
      id: "open-plan",
      label: "Open Treatment Plan",
      reason: "Opens the stored treatment plan.",
    };
  }
  if (input.workspace === "treatment-setup" && input.hasTreatment) {
    return {
      id: "open-staging",
      label: "Open Staging",
      reason: "Continue from the treatment plan into staging.",
    };
  }
  if (input.workspace === "staging" && input.hasTreatment) {
    return {
      id: "review-findings",
      label: "Review Findings",
      reason: "Open validation for the current plan.",
    };
  }
  if (input.workspace === "validation" && input.hasTreatment) {
    return {
      id: "export",
      label: "Export Package",
      reason: "Open production export.",
    };
  }
  return null;
}

export function layoutBudget(width: number, height: number): LayoutBudget {
  const header = 48;
  const pad = width <= 1440 ? 12 : 20;
  const rail = width <= 1440 ? 216 : 240;
  const inspector = width <= 1440 ? 248 : 280;
  const viewport = Math.max(0, width - rail - inspector - pad);
  return {
    header,
    rail,
    inspector,
    viewport,
    viewportDominant: viewport > rail && viewport > inspector && height >= 700,
    pageScroll: false,
  };
}

export function singleStatusSurface(markers: readonly string[]): boolean {
  return markers.filter((marker) => marker === "primary").length === 1;
}

/** Guard used by tests: synthetic gingiva must not be copied into clinical payloads. */
export function clinicalPayloadOmitsSyntheticGingiva(payload: object): boolean {
  return !Object.prototype.hasOwnProperty.call(payload, "gingiva") && !JSON.stringify(payload).includes("\"vertices\"");
}
