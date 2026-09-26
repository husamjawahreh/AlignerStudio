/**
 * Wave 5 next-action resolver.
 *
 * One deterministic action from persisted UI state. The action is included
 * only when the workspace can execute it. It does not invent clinical work.
 */

import type { SegmentationEvidenceKind } from "./model";
import type { WorkflowStepId } from "../workflow";

export type NextActionId =
  | "create-case"
  | "import-scans"
  | "resolve-segmentation-environment"
  | "retry-segmentation"
  | "review-segmentation"
  | "review-unresolved"
  | "review-treatment-dependency"
  | "create-treatment-plan"
  | "open-treatment-plan"
  | "regenerate-staging"
  | "refresh-validation"
  | "review-production"
  | "open-staging"
  | "review-findings"
  | "export-package"
  | "cancel-processing";

export interface NextAction {
  id: NextActionId;
  label: string;
  reason: string;
  step: WorkflowStepId;
  executable: true;
  /** False when the current step already shows this control, or cancel lives on the processing overlay. */
  showInHeader: boolean;
}

export interface NextActionInput {
  workspace: WorkflowStepId;
  hasCase: boolean;
  upperReady: boolean;
  lowerReady: boolean;
  segmentationKind: SegmentationEvidenceKind;
  /** Null when instance counts are not established. */
  unresolvedIdentityCount: number | null;
  hasTreatment: boolean;
  stagingFreshness: "stale" | "current" | "unavailable" | null;
  validationFreshness: "stale" | "current" | "unavailable" | null;
  productionReachable: boolean;
  productionLimited: boolean;
  isBusy: boolean;
  stageStatus: string | null;
  canCancelProcessing: boolean;
  canRegenerateStaging: boolean;
  canRefreshValidation: boolean;
}

const CLINICAL_LABELS = new Set<string>([
  "Create Case",
  "Import upper and lower scans",
  "Import upper scan",
  "Import lower scan",
  "Review segmentation blocker",
  "Retry segmentation",
  "Review segmentation",
  "Review unresolved identities",
  "Review treatment setup dependency",
  "Create Treatment Plan",
  "Open Treatment Plan",
  "Generate / Regenerate Staging",
  "Dynamic staging refresh",
  "Review production limits",
  "Open Staging",
  "Review Findings",
  "Export Package",
  "Cancel processing",
]);

export function isKnownNextActionLabel(label: string): boolean {
  return CLINICAL_LABELS.has(label);
}

function formOwns(id: NextActionId, workspace: WorkflowStepId): boolean {
  switch (id) {
    case "create-case":
      return workspace === "case-intake";
    case "review-segmentation":
    case "retry-segmentation":
      return workspace === "case-intake" || workspace === "analysis";
    case "create-treatment-plan":
    case "open-treatment-plan":
      return workspace === "case-intake" || workspace === "treatment-setup";
    case "regenerate-staging":
    case "refresh-validation":
    case "open-staging":
      return workspace === "staging";
    case "review-findings":
      return workspace === "validation";
    case "export-package":
      return workspace === "production";
    case "cancel-processing":
      return true;
    default:
      return false;
  }
}

function action(
  partial: Omit<NextAction, "executable" | "showInHeader">,
  workspace: WorkflowStepId,
): NextAction {
  return {
    ...partial,
    executable: true,
    showInHeader: !formOwns(partial.id, workspace),
  };
}

function importLabel(upperReady: boolean, lowerReady: boolean): string {
  if (!upperReady && !lowerReady) return "Import upper and lower scans";
  if (!upperReady) return "Import upper scan";
  return "Import lower scan";
}

function segmentationNeedsRetry(
  kind: SegmentationEvidenceKind,
  stage: string,
): boolean {
  if (kind === "real_model_inference" || kind === "fixture_test_only" || kind === "requires_review") {
    return false;
  }
  return (
    kind === "failed" ||
    kind === "not_available" ||
    stage === "FAILED" ||
    stage === "CANCELLED" ||
    stage === "STALE" ||
    stage === "INTERRUPTED"
  );
}

/**
 * First matching executable action wins.
 * Busy local work yields no action. A server job that can be cancelled yields Cancel processing.
 */
export function resolveNextAction(input: NextActionInput): NextAction | null {
  const stage = (input.stageStatus ?? "").toUpperCase();

  if (stage === "PROCESSING" && input.canCancelProcessing) {
    return action(
      {
        id: "cancel-processing",
        label: "Cancel processing",
        reason: "Stops the current job. Source scans stay imported. A later run is a new job.",
        step: input.workspace,
      },
      input.workspace,
    );
  }

  if (input.isBusy) return null;

  if (!input.hasCase) {
    return action(
      {
        id: "create-case",
        label: "Create Case",
        reason: "Creates a case record. No scan is imported by this action.",
        step: "case-intake",
      },
      input.workspace,
    );
  }

  if (!input.upperReady || !input.lowerReady) {
    return action(
      {
        id: "import-scans",
        label: importLabel(input.upperReady, input.lowerReady),
        reason: "Crown STL for each missing arch. Bite registration is not part of this import.",
        step: "case-intake",
      },
      input.workspace,
    );
  }

  if (input.segmentationKind === "blocked_by_environment") {
    return action(
      {
        id: "resolve-segmentation-environment",
        label: "Review segmentation blocker",
        reason:
          "The host runtime is blocked. This is not a model failure and not zero teeth. Retry stays unavailable until that blocker is gone.",
        step: "analysis",
      },
      input.workspace,
    );
  }

  if (input.segmentationKind === "not_run") {
    return action(
      {
        id: "review-segmentation",
        label: "Review segmentation",
        reason: "Runs segmentation review for the imported scans. It does not assign clinical FDI.",
        step: "analysis",
      },
      input.workspace,
    );
  }

  if (
    input.workspace === "treatment-setup" &&
    !input.hasTreatment &&
    input.segmentationKind !== "real_model_inference" &&
    input.segmentationKind !== "fixture_test_only" &&
    input.segmentationKind !== "requires_review"
  ) {
    return action(
      {
        id: "review-treatment-dependency",
        label: "Review treatment setup dependency",
        reason: "No treatment target is stored. Setup stays dependent on a segmentation result. This action does not create a plan.",
        step: "treatment-setup",
      },
      input.workspace,
    );
  }

  if (segmentationNeedsRetry(input.segmentationKind, stage)) {
    return action(
      {
        id: "retry-segmentation",
        label: "Retry segmentation",
        reason: "Starts a new segmentation job. There is no mid-stage resume. The previous failure stays until the new job returns.",
        step: "analysis",
      },
      input.workspace,
    );
  }

  const instancesReady =
    input.segmentationKind === "real_model_inference" ||
    input.segmentationKind === "fixture_test_only" ||
    input.segmentationKind === "requires_review";

  if (instancesReady && input.unresolvedIdentityCount != null && input.unresolvedIdentityCount > 0) {
    return action(
      {
        id: "review-unresolved",
        label: "Review unresolved identities",
        reason:
          input.segmentationKind === "fixture_test_only"
            ? "Fixture or test-only output. Identity stays on tooth_ref. This is not patient inference, and no correction tool exists."
            : "Some identities are unresolved. Review tooth_ref. No FDI is invented, and no correction tool exists.",
        step: "analysis",
      },
      input.workspace,
    );
  }

  if (!input.hasTreatment) {
    if (!instancesReady) {
      return action(
        {
          id: "review-treatment-dependency",
          label: "Review treatment setup dependency",
          reason: "No treatment target is stored. Opening setup shows that dependency. This action does not create a plan.",
          step: "treatment-setup",
        },
        input.workspace,
      );
    }
    return action(
      {
        id: "create-treatment-plan",
        label: "Create Treatment Plan",
        reason: "Creates a treatment plan from the current case. It does not approve the plan.",
        step: "treatment-setup",
      },
      input.workspace,
    );
  }

  if (input.stagingFreshness === "stale" && input.canRegenerateStaging) {
    return action(
      {
        id: "regenerate-staging",
        label: "Generate / Regenerate Staging",
        reason: "Rebuilds staging from the current treatment setup.",
        step: "staging",
      },
      input.workspace,
    );
  }

  if (input.validationFreshness === "stale" && input.canRefreshValidation) {
    return action(
      {
        id: "refresh-validation",
        label: "Dynamic staging refresh",
        reason: "Recomputes staging from the current plan. Validation updates only from that result. This is not a clinical approval.",
        step: "staging",
      },
      input.workspace,
    );
  }

  if (input.hasTreatment && input.workspace !== "treatment-setup" && input.workspace === "analysis") {
    return action(
      {
        id: "open-treatment-plan",
        label: "Open Treatment Plan",
        reason: "Opens the stored treatment plan.",
        step: "treatment-setup",
      },
      input.workspace,
    );
  }

  if (input.productionReachable && input.productionLimited && (input.workspace === "production" || input.workspace === "validation")) {
    return action(
      {
        id: "review-production",
        label: "Review production limits",
        reason: "Opens production so missing manufacturing capabilities stay visible. It does not create appliances.",
        step: "production",
      },
      input.workspace,
    );
  }

  if (
    input.hasTreatment &&
    (input.workspace === "treatment-setup" ||
      input.workspace === "analysis" ||
      input.workspace === "case-intake")
  ) {
    return action(
      {
        id: "open-staging",
        label: "Open Staging",
        reason: "Opens the stored staging for this treatment plan.",
        step: "staging",
      },
      input.workspace,
    );
  }

  if (input.workspace === "staging" || input.workspace === "refinement") {
    return action(
      {
        id: "review-findings",
        label: "Review Findings",
        reason: "Opens geometric validation. A missing finding is not a pass.",
        step: "validation",
      },
      input.workspace,
    );
  }

  if (input.workspace === "validation" && input.productionReachable) {
    return action(
      {
        id: input.productionLimited ? "review-production" : "export-package",
        label: input.productionLimited ? "Review production limits" : "Export Package",
        reason: input.productionLimited
          ? "Opens production so missing manufacturing capabilities stay visible."
          : "Opens the export package for the stored plan.",
        step: "production",
      },
      input.workspace,
    );
  }

  if (input.productionReachable && input.workspace !== "production") {
    return action(
      {
        id: "review-production",
        label: "Review production limits",
        reason: "Opens production. Capabilities that are not implemented stay unavailable.",
        step: "production",
      },
      input.workspace,
    );
  }

  return null;
}
