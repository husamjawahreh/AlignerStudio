/**
 * Wave 10 action ownership.
 *
 * Each listed action has one owner. The inspector explains state.
 * Buttons stay on the surface that already calls the shared command path.
 */

export interface ActionOwnership {
  action: string;
  owner: "workflow-header" | "left-step-form" | "contextual-toolbar" | "tooth-toolbar" | "inspector" | "processing-overlay";
  condition: string;
  duplicateRemoved: string;
}

export const ACTION_OWNERSHIP: readonly ActionOwnership[] = [
  {
    action: "workflow-navigation",
    owner: "workflow-header",
    condition: "always",
    duplicateRemoved: "Inspector does not render step buttons",
  },
  {
    action: "create-case",
    owner: "left-step-form",
    condition: "case intake, no case",
    duplicateRemoved: "Inspector next row is text, not a second Create Case button",
  },
  {
    action: "scan-preparation",
    owner: "left-step-form",
    condition: "case intake with an uploaded scan",
    duplicateRemoved: "Inspector shows preparation status and does not apply orientation, trim, or cleanup",
  },
  {
    action: "segmentation-candidate-review",
    owner: "left-step-form",
    condition: "case intake after an accepted prepared artifact",
    duplicateRemoved: "Inspector shows segmentation status and does not start segmentation or edit instances",
  },
  {
    action: "review-segmentation",
    owner: "left-step-form",
    condition: "analysis",
    duplicateRemoved: "Right analysis inspector removed",
  },
  {
    action: "retry-segmentation",
    owner: "contextual-toolbar",
    condition: "failed, cancelled, or interrupted",
    duplicateRemoved: "Inspector lists no Retry button. Blocked environment still withholds retry",
  },
  {
    action: "create-treatment-plan",
    owner: "left-step-form",
    condition: "treatment setup",
    duplicateRemoved: "Inspector does not generate a plan",
  },
  {
    action: "save-restore-compare",
    owner: "left-step-form",
    condition: "treatment setup with a stored plan",
    duplicateRemoved: "Right setup inspector no longer repeats version buttons",
  },
  {
    action: "regenerate-staging",
    owner: "left-step-form",
    condition: "staging",
    duplicateRemoved: "Toolbar suppresses regenerate on the staging step",
  },
  {
    action: "fit-isolate-camera",
    owner: "contextual-toolbar",
    condition: "scene available",
    duplicateRemoved: "Inspector action list no longer names Fit or Isolate",
  },
  {
    action: "move-rotate",
    owner: "tooth-toolbar",
    condition: "one tooth in Treatment Setup or Refinement",
    duplicateRemoved: "Left refinement Move and Rotate buttons removed",
  },
  {
    action: "numeric-edit-lock-exclude-apply-reset-undo-redo",
    owner: "inspector",
    condition: "one editable tooth",
    duplicateRemoved: "Tooth toolbar hides lock, exclude, apply, and cancel while the inspector is mounted",
  },
  {
    action: "reset-all-edits",
    owner: "inspector",
    condition: "refinement with a stored plan",
    duplicateRemoved: "No second reset-all control",
  },
  {
    action: "ipr-attachment-review",
    owner: "inspector",
    condition: "refinement, collapsed until opened",
    duplicateRemoved: "Proposal editors removed from Treatment Setup",
  },
  {
    action: "cancel-processing",
    owner: "processing-overlay",
    condition: "job running",
    duplicateRemoved: "Toolbar cancel is suppressed while the overlay is up",
  },
  {
    action: "remaining-time",
    owner: "processing-overlay",
    condition: "job running",
    duplicateRemoved: "Inspector does not repeat the estimate or invent an ETA",
  },
  {
    action: "export",
    owner: "left-step-form",
    condition: "production",
    duplicateRemoved: "Right export panel removed",
  },
];

export function ownersFor(action: string): string[] {
  return ACTION_OWNERSHIP.filter((row) => row.action === action).map((row) => row.owner);
}
