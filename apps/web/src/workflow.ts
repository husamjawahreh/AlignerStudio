export type WorkflowStepId =
  | "case"
  | "analysis"
  | "segmentation"
  | "treatment-plan"
  | "stage-review"
  | "tooth-editor"
  | "validation"
  | "export";

export type WorkflowStepStatus = "current" | "complete" | "blocked" | "ready" | "pending";

export interface WorkflowStep {
  id: WorkflowStepId;
  label: string;
  status: WorkflowStepStatus;
  attentionCount?: number;
}

export interface WorkflowAction {
  label: string;
  step: WorkflowStepId;
  disabled?: boolean;
}

export interface WorkflowSuggestion {
  title: string;
  detail: string;
  action?: WorkflowAction;
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
  const definitions: Array<[WorkflowStepId, string]> = [
    ["case", "Case"],
    ["analysis", "Understand"],
    ["segmentation", "Segmentation"],
    ["treatment-plan", "Plan"],
    ["stage-review", "Review"],
    ["tooth-editor", "Refine"],
    ["validation", "Validate"],
    ["export", "Export"],
  ];
  return definitions.map(([id, label]) => ({
    id,
    label,
    status: id === input.activeStep
      ? "current"
      : id === "case"
        ? (input.hasCase ? "complete" : "ready")
        : id === "analysis" || id === "segmentation"
          ? (input.hasSegmentation ? "complete" : input.bothArchesValid ? "ready" : "blocked")
          : id === "treatment-plan" || id === "stage-review"
            ? (input.hasTreatment ? "complete" : input.hasSegmentation ? "ready" : "blocked")
            : id === "tooth-editor"
              ? (input.editCount > 0 ? "complete" : input.hasTreatment ? "ready" : "blocked")
              : id === "validation"
                ? (input.hasValidation ? "complete" : input.hasTreatment ? "ready" : "blocked")
                : input.hasValidation ? "ready" : "blocked",
    attentionCount: id === "validation" && input.hasValidation ? 0 : undefined,
  }));
}
