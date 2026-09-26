/**
 * P2 — Professional Clinical-CAD Workflow
 * Master labels (v2.1): CASE INTAKE → ANALYSIS → TREATMENT SETUP →
 * STAGING → REFINEMENT → VALIDATION → PRODUCTION
 *
 * Wave 7 extends this module. resolveWorkflow is the only workflow-state
 * resolver. It does not start segmentation, planning, staging, or validation.
 */

import type { SegmentationEvidenceKind } from "./interaction/model";
import { resolveNextAction, type NextAction, type NextActionId } from "./interaction/nextAction";

export type WorkflowStepId =
  | "case-intake"
  | "analysis"
  | "treatment-setup"
  | "staging"
  | "refinement"
  | "validation"
  | "production";

export type WorkflowStepStatus = "current" | "complete" | "blocked" | "ready" | "pending";

/** Wave 7 lifecycle. Distinct from the legacy status projection. */
export type WorkflowLifecycle =
  | "not_started"
  | "available"
  | "active"
  | "completed"
  | "blocked"
  | "unavailable"
  | "stale"
  | "failed"
  | "requires_review";

export interface WorkflowEmptyState {
  /** What is missing. */
  missing: string;
  /** Why that matters. */
  why: string;
  /** What can be done now. */
  now: string;
}

export interface WorkflowStepNextAction {
  id: NextActionId;
  label: string;
  /** True when this step is where the canonical action runs. */
  appliesHere: boolean;
}

export interface WorkflowStep {
  id: WorkflowStepId;
  /** Display label matching Master Plan terminology. */
  label: string;
  /** Uppercase plan token for status chrome (e.g. CASE INTAKE). */
  planToken: string;
  /** Legacy projection used by older chrome tests. Prefer `state`. */
  status: WorkflowStepStatus;
  state: WorkflowLifecycle;
  current: boolean;
  /** Completion condition is met. Not a clinical approval. */
  satisfied: boolean;
  dependency: string;
  completionCondition: string;
  /** Canonical next action. The same object on every step. */
  nextAction: WorkflowStepNextAction | null;
  /** Why the step is blocked, unavailable, failed, or stale. */
  reason: string | null;
  navigationAllowed: boolean;
  emptyState: WorkflowEmptyState;
  attentionCount?: number;
}

export interface WorkflowAction {
  label: string;
  step: WorkflowStepId;
  disabled?: boolean;
}

/** Canonical P2 workflow definitions — labels must match Master Plan v2.1. */
export const WORKFLOW_DEFINITIONS: readonly {
  id: WorkflowStepId;
  label: string;
  planToken: string;
}[] = [
  { id: "case-intake", label: "Case Intake", planToken: "CASE INTAKE" },
  { id: "analysis", label: "Analysis", planToken: "ANALYSIS" },
  { id: "treatment-setup", label: "Treatment Setup", planToken: "TREATMENT SETUP" },
  { id: "staging", label: "Staging", planToken: "STAGING" },
  { id: "refinement", label: "Refinement", planToken: "REFINEMENT" },
  { id: "validation", label: "Validation", planToken: "VALIDATION" },
  { id: "production", label: "Production", planToken: "PRODUCTION" },
] as const;

export function workflowStepIndex(id: WorkflowStepId): number {
  return WORKFLOW_DEFINITIONS.findIndex((step) => step.id === id);
}

export function workflowLabel(id: WorkflowStepId): string {
  return WORKFLOW_DEFINITIONS.find((step) => step.id === id)?.label ?? id;
}

export function workflowPlanToken(id: WorkflowStepId): string {
  return WORKFLOW_DEFINITIONS.find((step) => step.id === id)?.planToken ?? id.toUpperCase();
}

export type WorkflowFreshness = "stale" | "current" | "unavailable" | null;

/** Persisted case and session facts. No geometry payloads. */
export interface WorkflowEvidence {
  activeStep: WorkflowStepId;
  hasCase: boolean;
  upperReady: boolean;
  lowerReady: boolean;
  segmentationKind: SegmentationEvidenceKind;
  hasTreatment: boolean;
  hasTarget: boolean;
  stagingFreshness: WorkflowFreshness;
  stagingCount: number;
  validationFreshness: WorkflowFreshness;
  hasValidationRun: boolean;
  productionReachable: boolean;
  productionLimited: boolean;
  editCount: number;
  isBusy: boolean;
  stageStatus: string | null;
  canCancelProcessing: boolean;
  canRegenerateStaging: boolean;
  canRefreshValidation: boolean;
  unresolvedIdentityCount: number | null;
}

export interface WorkflowResolution {
  steps: WorkflowStep[];
  /** Single next action for header, step form, and toolbar suppression. */
  nextAction: NextAction | null;
}

export type WorkflowNavigationIntent = "stay" | "review" | "enter" | "explain";

export interface WorkflowNavigationDecision {
  intent: WorkflowNavigationIntent;
  /** Navigate and inspect never start a long job. */
  operation: "navigate" | "inspect";
  reason: string | null;
  showDependency: boolean;
}

const INSTANCE_KINDS = new Set<SegmentationEvidenceKind>([
  "real_model_inference",
  "fixture_test_only",
  "requires_review",
]);

function scansReady(evidence: WorkflowEvidence): boolean {
  return evidence.upperReady && evidence.lowerReady;
}

function instancesReady(kind: SegmentationEvidenceKind): boolean {
  return INSTANCE_KINDS.has(kind);
}

/** In-progress steps become active. Terminal conditions stay visible while current. */
function presentState(condition: WorkflowLifecycle, current: boolean): WorkflowLifecycle {
  if (!current) return condition;
  if (condition === "not_started" || condition === "available") return "active";
  return condition;
}

function legacyStatus(state: WorkflowLifecycle, current: boolean): WorkflowStepStatus {
  if (current) return "current";
  if (state === "completed") return "complete";
  if (state === "available" || state === "stale" || state === "requires_review") return "ready";
  if (state === "not_started") return "pending";
  return "blocked";
}

interface StepDraft {
  state: WorkflowLifecycle;
  satisfied: boolean;
  navigationAllowed: boolean;
  dependency: string;
  completionCondition: string;
  reason: string | null;
  emptyState: WorkflowEmptyState;
}

function caseIntakeDraft(evidence: WorkflowEvidence): StepDraft {
  const ready = scansReady(evidence);
  const satisfied = evidence.hasCase && ready;
  const condition: WorkflowLifecycle = !evidence.hasCase ? "not_started" : ready ? "completed" : "available";
  return {
    state: presentState(condition, evidence.activeStep === "case-intake"),
    satisfied,
    navigationAllowed: true,
    dependency: "Launch always opens case intake.",
    completionCondition: "A case exists and both scans are imported.",
    reason: !evidence.hasCase ? "No case is open." : ready ? null : "The case needs an upper scan and a lower scan.",
    emptyState: !evidence.hasCase
      ? {
          missing: "Case",
          why: "The rest of the workflow belongs to a case.",
          now: "Create a case. That does not import a scan.",
        }
      : ready
        ? {
            missing: "Nothing else for intake",
            why: "Both scans are on this case.",
            now: "Open segmentation review when you want to. Opening it does not start segmentation.",
          }
        : {
            missing: "Upper and lower scans",
            why: "Segmentation review needs both scans.",
            now: "Import the missing scan.",
          },
  };
}

function analysisDraft(evidence: WorkflowEvidence): StepDraft {
  const current = evidence.activeStep === "analysis";
  const dependency = "Imported upper and lower scans.";
  const completionCondition =
    "Segmentation evidence from the installed model is stored. A test-only result does not complete this step.";
  if (!evidence.hasCase || !scansReady(evidence)) {
    return {
      state: presentState("blocked", current),
      satisfied: false,
      navigationAllowed: false,
      dependency,
      completionCondition,
      reason: evidence.hasCase
        ? "Import both scans before segmentation review."
        : "Create a case before segmentation review.",
      emptyState: {
        missing: "Both scans",
        why: "Segmentation review reads the imported scans.",
        now: "Return to case intake and import the missing scan.",
      },
    };
  }
  const stage = (evidence.stageStatus ?? "").toUpperCase();
  if (evidence.segmentationKind === "blocked_by_environment") {
    return {
      state: presentState("blocked", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason:
        "Segmentation cannot be completed on this computer. This is not a failed scan and not zero teeth.",
      emptyState: {
        missing: "Segmentation on this computer",
        why: "The segmentation runtime is blocked, so tooth instances are not available.",
        now: "Review this blocker. Retry stays unavailable until the computer can run segmentation.",
      },
    };
  }
  if (evidence.segmentationKind === "failed" || stage === "FAILED") {
    return {
      state: presentState("failed", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Segmentation failed. The previous result stays until a new run finishes.",
      emptyState: {
        missing: "A successful segmentation review",
        why: "Failed segmentation is not tooth evidence.",
        now: "Retry segmentation only if you want a new run. Opening this step does not start one.",
      },
    };
  }
  if (evidence.segmentationKind === "not_available") {
    return {
      state: presentState("unavailable", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Segmentation is not available for these scans.",
      emptyState: {
        missing: "Segmentation",
        why: "No segmentation result is available to review.",
        now: "There is no tooth list to treat as missing teeth.",
      },
    };
  }
  if (evidence.segmentationKind === "fixture_test_only") {
    return {
      state: presentState("requires_review", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "This segmentation is test-only. It is not a patient result.",
      emptyState: {
        missing: "Patient segmentation",
        why: "The meshes on screen are for interface review.",
        now: "Review them as test-only. Do not treat them as a clinical segmentation.",
      },
    };
  }
  if (evidence.segmentationKind === "requires_review") {
    return {
      state: presentState("requires_review", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Segmentation is stored and still needs review.",
      emptyState: {
        missing: "A reviewed segmentation",
        why: "Identity that is not established stays unresolved.",
        now: "Review the segmentation. No numbering is invented.",
      },
    };
  }
  if (evidence.segmentationKind === "real_model_inference") {
    return {
      state: presentState("completed", current),
      satisfied: true,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: null,
      emptyState: {
        missing: "Nothing else required to review segmentation",
        why: "Segmentation evidence is stored.",
        now: "Review it, then continue to treatment setup when you are ready.",
      },
    };
  }
  return {
    state: presentState("not_started", current),
    satisfied: false,
    navigationAllowed: true,
    dependency,
    completionCondition,
    reason: "Segmentation has not been run.",
    emptyState: {
      missing: "Segmentation review",
      why: "Treatment setup needs segmentation evidence before a target can be planned.",
      now: "Choose Review segmentation when you want a run. Opening this step does not start one.",
    },
  };
}

function treatmentDraft(evidence: WorkflowEvidence): StepDraft {
  const current = evidence.activeStep === "treatment-setup";
  const dependency = "Segmentation evidence for tooth-level planning.";
  const completionCondition = "A treatment plan and target are stored. Opening the step does not create one.";
  if (!evidence.hasCase || !scansReady(evidence)) {
    return {
      state: presentState("blocked", current),
      satisfied: false,
      navigationAllowed: false,
      dependency,
      completionCondition,
      reason: "Import both scans before treatment setup.",
      emptyState: {
        missing: "Both scans",
        why: "Treatment setup cannot start from an empty case.",
        now: "Finish case intake. This step does not create a plan.",
      },
    };
  }
  if (!instancesReady(evidence.segmentationKind) && !evidence.hasTreatment) {
    const environment = evidence.segmentationKind === "blocked_by_environment";
    return {
      state: presentState("unavailable", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: environment
        ? "Segmentation is blocked by environment. Tooth-level setup is unavailable on this computer."
        : "No segmentation evidence is stored, so there is no treatment target.",
      emptyState: {
        missing: "Treatment target",
        why: environment
          ? "Segmentation cannot be completed on this computer, so a target cannot be planned from tooth instances."
          : "A target is planned from segmentation evidence. None is stored.",
        now: "Review the segmentation dependency. Opening treatment setup does not create a plan.",
      },
    };
  }
  if (!evidence.hasTreatment || !evidence.hasTarget) {
    return {
      state: presentState(evidence.hasTreatment ? "requires_review" : "available", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: evidence.hasTreatment
        ? "A plan is stored, but no target geometry is available."
        : "No treatment target is stored.",
      emptyState: {
        missing: "Treatment target",
        why: "Staging and later steps use the stored target.",
        now: evidence.hasTreatment
          ? "Review the stored plan. This page does not rebuild it."
          : "Create a treatment plan only with the explicit action. Opening this step does not create one.",
      },
    };
  }
  return {
    state: presentState("completed", current),
    satisfied: true,
    navigationAllowed: true,
    dependency,
    completionCondition,
    reason: null,
    emptyState: {
      missing: "Nothing else required to review the plan",
      why: "A target is stored.",
      now: "Review the plan. Opening this step does not rebuild staging or validation.",
    },
  };
}

function stagingDraft(evidence: WorkflowEvidence): StepDraft {
  const current = evidence.activeStep === "staging";
  const dependency = "A stored treatment target.";
  const completionCondition = "Stages are stored for the current target and are not out of date.";
  if (!evidence.hasTreatment) {
    return {
      state: presentState("blocked", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Staging needs a stored treatment target.",
      emptyState: {
        missing: "Treatment target",
        why: "Stages are built from the target. There is no target yet.",
        now: "Open treatment setup. Opening staging does not build stages.",
      },
    };
  }
  if (evidence.stagingFreshness === "stale") {
    return {
      state: presentState("stale", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Stages are out of date relative to the treatment setup.",
      emptyState: {
        missing: "Current stages",
        why: "The stored stages do not match the current target.",
        now: "Regenerate staging when you choose to. Opening this step does not rebuild them.",
      },
    };
  }
  if (evidence.stagingCount <= 0 || evidence.stagingFreshness !== "current") {
    const unknown = evidence.stagingFreshness == null || evidence.stagingFreshness === "unavailable";
    return {
      state: presentState(evidence.stagingCount <= 0 ? "not_started" : "unavailable", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason:
        evidence.stagingCount <= 0
          ? "No stages are stored for this treatment setup."
          : "Staging freshness is not available.",
      emptyState: {
        missing: evidence.stagingCount <= 0 ? "Stages" : "A current staging result",
        why: unknown
          ? "Stored stages cannot be confirmed against the target."
          : "There is a target, but no stage sequence is stored.",
        now: "Generate staging only with the explicit action. Opening this step does not rebuild stages.",
      },
    };
  }
  return {
    state: presentState("completed", current),
    satisfied: true,
    navigationAllowed: true,
    dependency,
    completionCondition,
    reason: null,
    emptyState: {
      missing: "Nothing else required to review stages",
      why: `${evidence.stagingCount} stages are stored for the current target.`,
      now: "Review the stages. This is not a claim of clinical optimality.",
    },
  };
}

function refinementDraft(evidence: WorkflowEvidence): StepDraft {
  const current = evidence.activeStep === "refinement";
  const dependency = "A stored treatment plan.";
  const completionCondition = "A durable edit exists. Editing stays optional.";
  if (!evidence.hasTreatment) {
    return {
      state: presentState("blocked", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Refinement needs a stored treatment plan.",
      emptyState: {
        missing: "Treatment plan",
        why: "Tooth edits apply to a stored plan.",
        now: "Open treatment setup. This step does not create a plan.",
      },
    };
  }
  const edited = evidence.editCount > 0;
  return {
    state: presentState(edited ? "completed" : "available", current),
    satisfied: edited,
    navigationAllowed: true,
    dependency,
    completionCondition,
    reason: null,
    emptyState: {
      missing: edited ? "Nothing else required to keep editing" : "Edits, if you want them",
      why: "Move, rotate, lock, exclude, reset, and undo apply to the stored plan.",
      now: "Select a tooth to edit. Opening this step does not move teeth.",
    },
  };
}

function validationDraft(evidence: WorkflowEvidence): StepDraft {
  const current = evidence.activeStep === "validation";
  const dependency = "A stored treatment plan.";
  const completionCondition = "A validation run is stored for the current treatment version. A run is not an approval.";
  if (!evidence.hasTreatment) {
    return {
      state: presentState("blocked", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Validation needs a stored treatment plan.",
      emptyState: {
        missing: "Treatment plan",
        why: "Findings are computed for a treatment version.",
        now: "Open treatment setup. Opening validation does not start a run.",
      },
    };
  }
  if (evidence.validationFreshness === "stale") {
    return {
      state: presentState("stale", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Validation is out of date for the current treatment version.",
      emptyState: {
        missing: "A current validation run",
        why: "The stored findings do not match the current treatment version.",
        now: "Refresh validation when you choose to. Opening this step does not refresh it.",
      },
    };
  }
  if (!evidence.hasValidationRun) {
    return {
      state: presentState("not_started", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "No validation run is stored for this treatment version.",
      emptyState: {
        missing: "Validation run",
        why: "There is nothing to review until a run exists.",
        now: "A missing check is not a pass. Opening this step does not start validation.",
      },
    };
  }
  if (evidence.validationFreshness !== "current") {
    return {
      state: presentState("unavailable", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Some validation checks are unavailable.",
      emptyState: {
        missing: "Unavailable checks",
        why: "A check that did not run is not a pass.",
        now: "Review the checks that exist. Do not treat the rest as clear.",
      },
    };
  }
  return {
    state: presentState("completed", current),
    satisfied: true,
    navigationAllowed: true,
    dependency,
    completionCondition,
    reason: null,
    emptyState: {
      missing: "Nothing else required to review findings",
      why: "A validation run is stored. That is not a clinical approval.",
      now: "Review the findings and the checks that could not run.",
    },
  };
}

function productionDraft(evidence: WorkflowEvidence): StepDraft {
  const current = evidence.activeStep === "production";
  const dependency = "A stored treatment plan.";
  const completionCondition =
    "Production stays incomplete while manufacturing capabilities are unavailable. Export is not manufacturing certification.";
  if (!evidence.hasTreatment) {
    return {
      state: presentState("blocked", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Production needs a stored treatment plan.",
      emptyState: {
        missing: "Treatment plan",
        why: "Export is built from a stored plan.",
        now: "Open treatment setup. This step does not create appliances.",
      },
    };
  }
  if (!evidence.productionReachable || evidence.productionLimited) {
    return {
      state: presentState("requires_review", current),
      satisfied: false,
      navigationAllowed: true,
      dependency,
      completionCondition,
      reason: "Manufacturing capabilities are still unavailable. This is not manufacturing readiness.",
      emptyState: {
        missing: "Manufacturing capabilities",
        why: "The plan can be reviewed, but appliance manufacturing is not available.",
        now: "Review the production limits. Do not treat export as a finished appliance.",
      },
    };
  }
  return {
    state: presentState("available", current),
    satisfied: false,
    navigationAllowed: true,
    dependency,
    completionCondition,
    reason: "Export can be reviewed. Manufacturing certification is not claimed.",
    emptyState: {
      missing: "Manufacturing certification",
      why: "An engineering export is not a finished appliance.",
      now: "Review the package and the limits that remain.",
    },
  };
}

const DRAFTS: Record<WorkflowStepId, (evidence: WorkflowEvidence) => StepDraft> = {
  "case-intake": caseIntakeDraft,
  analysis: analysisDraft,
  "treatment-setup": treatmentDraft,
  staging: stagingDraft,
  refinement: refinementDraft,
  validation: validationDraft,
  production: productionDraft,
};

function canonicalNextAction(evidence: WorkflowEvidence): NextAction | null {
  return resolveNextAction({
    workspace: evidence.activeStep,
    hasCase: evidence.hasCase,
    upperReady: evidence.upperReady,
    lowerReady: evidence.lowerReady,
    segmentationKind: evidence.segmentationKind,
    unresolvedIdentityCount: evidence.unresolvedIdentityCount,
    hasTreatment: evidence.hasTreatment,
    stagingFreshness: evidence.stagingFreshness,
    validationFreshness: evidence.validationFreshness,
    productionReachable: evidence.productionReachable,
    productionLimited: evidence.productionLimited,
    isBusy: evidence.isBusy,
    stageStatus: evidence.stageStatus,
    canCancelProcessing: evidence.canCancelProcessing,
    canRegenerateStaging: evidence.canRegenerateStaging,
    canRefreshValidation: evidence.canRefreshValidation,
  });
}

/** One workflow resolution from persisted facts. Does not load geometry or start work. */
export function resolveWorkflow(evidence: WorkflowEvidence): WorkflowResolution {
  const nextAction = canonicalNextAction(evidence);
  const shared = nextAction ? { id: nextAction.id, label: nextAction.label } : null;
  const steps = WORKFLOW_DEFINITIONS.map(({ id, label, planToken }) => {
    const draft = DRAFTS[id](evidence);
    const current = evidence.activeStep === id;
    return {
      id,
      label,
      planToken,
      status: legacyStatus(draft.state, current),
      state: draft.state,
      current,
      satisfied: draft.satisfied,
      dependency: draft.dependency,
      completionCondition: draft.completionCondition,
      nextAction: shared ? { ...shared, appliesHere: nextAction?.step === id } : null,
      reason: draft.reason,
      navigationAllowed: draft.navigationAllowed,
      emptyState: draft.emptyState,
      attentionCount: id === "validation" && evidence.hasValidationRun ? 0 : undefined,
    };
  });
  return { steps, nextAction };
}

export function resolveWorkflowNavigation(
  steps: readonly WorkflowStep[],
  targetId: WorkflowStepId,
): WorkflowNavigationDecision {
  const target = steps.find((step) => step.id === targetId);
  const current = steps.find((step) => step.current);
  if (!target || !current || target.id === current.id) {
    return { intent: "stay", operation: "navigate", reason: null, showDependency: false };
  }
  if (!target.navigationAllowed) {
    return {
      intent: "explain",
      operation: "inspect",
      reason: target.reason ?? target.emptyState.why,
      showDependency: true,
    };
  }
  const earlier = workflowStepIndex(target.id) < workflowStepIndex(current.id);
  const terminal =
    target.state === "blocked" || target.state === "unavailable" || target.state === "failed";
  return {
    intent: earlier ? "review" : "enter",
    operation: "navigate",
    reason: terminal ? target.reason : null,
    showDependency: terminal,
  };
}

export function workflowStepFromHistory(state: unknown): WorkflowStepId | null {
  if (!state || typeof state !== "object" || !("workflowStep" in state)) return null;
  const value = (state as { workflowStep?: unknown }).workflowStep;
  if (typeof value !== "string") return null;
  return WORKFLOW_DEFINITIONS.some((step) => step.id === value) ? (value as WorkflowStepId) : null;
}

export function buildWorkflowSteps(input: {
  activeStep: WorkflowStepId;
  hasCase: boolean;
  bothArchesValid: boolean;
  hasSegmentation: boolean;
  hasTreatment: boolean;
  editCount: number;
  hasValidation: boolean;
}): WorkflowStep[] {
  return resolveWorkflow({
    activeStep: input.activeStep,
    hasCase: input.hasCase,
    upperReady: input.bothArchesValid,
    lowerReady: input.bothArchesValid,
    segmentationKind: input.hasSegmentation ? "real_model_inference" : "not_run",
    hasTreatment: input.hasTreatment,
    hasTarget: input.hasTreatment,
    stagingFreshness: input.hasTreatment ? "current" : null,
    stagingCount: input.hasTreatment ? 1 : 0,
    validationFreshness: input.hasValidation ? "current" : null,
    hasValidationRun: input.hasValidation,
    productionReachable: input.hasTreatment,
    productionLimited: input.hasTreatment,
    editCount: input.editCount,
    isBusy: false,
    stageStatus: null,
    canCancelProcessing: false,
    canRegenerateStaging: input.hasTreatment,
    canRefreshValidation: input.hasTreatment,
    unresolvedIdentityCount: input.hasSegmentation ? 0 : null,
  }).steps;
}

/** Contextual primary actions shown for the active step (existing capabilities only). */
export function buildWorkflowActions(input: {
  activeStep: WorkflowStepId;
  hasCase: boolean;
  bothArchesValid: boolean;
  hasSegmentation: boolean;
  hasTreatment: boolean;
  isBusy: boolean;
}): WorkflowAction[] {
  switch (input.activeStep) {
    case "case-intake":
      if (input.hasCase) {
        return [
          {
            label: "Scan Import",
            step: "case-intake",
            disabled: input.isBusy,
          },
        ];
      }
      return [
        {
          label: "Create Case",
          step: "case-intake",
          disabled: input.isBusy,
        },
      ];
    case "analysis":
      return [
        {
          label: "Analyze case",
          step: "analysis",
          disabled: !input.bothArchesValid || input.isBusy,
        },
      ];
    case "treatment-setup":
      return [
        {
          label: input.hasTreatment ? "Open Treatment Plan" : "Create Treatment Plan",
          step: "treatment-setup",
          disabled: !input.bothArchesValid || input.isBusy,
        },
      ];
    case "staging":
      return [
        {
          label: "Open Staging",
          step: "staging",
          disabled: !input.hasTreatment,
        },
      ];
    case "refinement":
      return [
        {
          label: "Open Refinement",
          step: "refinement",
          disabled: !input.hasTreatment,
        },
      ];
    case "validation":
      return [
        {
          label: "Review Findings",
          step: "validation",
          disabled: !input.hasTreatment,
        },
      ];
    case "production":
      return [
        {
          label: "Export Package",
          step: "production",
          disabled: !input.hasTreatment,
        },
      ];
    default:
      return [];
  }
}
