/**
 * P2 — Professional Clinical-CAD Workflow
 * Master labels (v2.1): CASE INTAKE → ANALYSIS → TREATMENT SETUP →
 * STAGING → REFINEMENT → VALIDATION → PRODUCTION
 */

export type WorkflowStepId =
  | "case-intake"
  | "analysis"
  | "treatment-setup"
  | "staging"
  | "refinement"
  | "validation"
  | "production";

export type WorkflowStepStatus = "current" | "complete" | "blocked" | "ready" | "pending";

export interface WorkflowStep {
  id: WorkflowStepId;
  /** Display label matching Master Plan terminology. */
  label: string;
  /** Uppercase plan token for status chrome (e.g. CASE INTAKE). */
  planToken: string;
  status: WorkflowStepStatus;
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

export function buildWorkflowSteps(input: {
  activeStep: WorkflowStepId;
  hasCase: boolean;
  bothArchesValid: boolean;
  hasSegmentation: boolean;
  hasTreatment: boolean;
  editCount: number;
  hasValidation: boolean;
}): WorkflowStep[] {
  return WORKFLOW_DEFINITIONS.map(({ id, label, planToken }) => ({
    id,
    label,
    planToken,
    status:
      id === input.activeStep
        ? "current"
        : id === "case-intake"
          ? input.hasCase
            ? "complete"
            : "ready"
          : id === "analysis"
            ? input.hasSegmentation
              ? "complete"
              : input.bothArchesValid
                ? "ready"
                : "blocked"
            : id === "treatment-setup"
              ? input.hasTreatment
                ? "complete"
                : input.hasSegmentation || input.bothArchesValid
                  ? "ready"
                  : "blocked"
              : id === "staging"
                ? input.hasTreatment
                  ? "complete"
                  : input.hasSegmentation
                    ? "ready"
                    : "blocked"
                : id === "refinement"
                  ? input.editCount > 0
                    ? "complete"
                    : input.hasTreatment
                      ? "ready"
                      : "blocked"
                  : id === "validation"
                    ? input.hasValidation
                      ? "complete"
                      : input.hasTreatment
                        ? "ready"
                        : "blocked"
                    : input.hasTreatment
                      ? input.hasValidation
                        ? "complete"
                        : "ready"
                      : "blocked",
    attentionCount: id === "validation" && input.hasValidation ? 0 : undefined,
  }));
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
          label: "Review Treatment Setup",
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
