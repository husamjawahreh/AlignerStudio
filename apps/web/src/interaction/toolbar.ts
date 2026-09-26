/**
 * Wave 6 canonical contextual toolbar.
 *
 * One resolver decides every viewport tool. Buttons call the existing
 * command ids. They do not mutate treatment data by themselves.
 */

import type { SegmentationEvidenceKind, WorkspaceShortcut } from "./model";
import type { WorkflowStepId } from "../workflow";

export type ToolbarContextId =
  | "idle"
  | "one-tooth"
  | "multi-tooth"
  | "case"
  | "segmentation-review"
  | "treatment-setup"
  | "staging"
  | "refinement"
  | "validation"
  | "production"
  | "processing"
  | "blocked"
  | "failed"
  | "stale"
  | "unavailable";

/** Distinct from a disabled button. Unavailable is not the same as blocked or stale. */
export type ActionAvailability = "available" | "unavailable" | "blocked" | "requires_review" | "stale";

export type ActionCategory = "workflow" | "selection" | "manipulation" | "viewport" | "review" | "utility" | "advanced";

/** 1 is the immediate workflow action. 7 is advanced technical. */
export type ActionPriority = 1 | 2 | 3 | 4 | 5 | 6 | 7;

export type ActionEffect = "view" | "selection" | "durable-edit" | "job";

export interface ToolbarAction {
  id: string;
  label: string;
  category: ActionCategory;
  availability: ActionAvailability;
  reason: string;
  priority: ActionPriority;
  shortcut?: string;
  /** Clinical undo only for durable edits. Viewport commands are not clinical undo. */
  effect: ActionEffect;
  reversible: boolean;
  destructive: false;
  truthDependency: string | null;
  active?: boolean;
  executable: boolean;
  placement: "primary" | "more" | "withheld";
}

export interface ToolbarMachineInput {
  workspace: WorkflowStepId;
  hasCase: boolean;
  sceneAvailable: boolean;
  segmentationKind: SegmentationEvidenceKind;
  selectionCount: number;
  groupIdentity: "same" | "mixed" | null;
  archMode: "upper" | "lower" | "both";
  isolateActive: boolean;
  labelMode: "off" | "selected" | "arch" | "all";
  gingivaVisible: boolean;
  segmentationVisible: boolean;
  wireframe: boolean;
  movementVisible: boolean;
  targetVisible: boolean;
  treatmentAvailable: boolean;
  targetGeometryExists: boolean;
  validationAvailable: boolean;
  validationFindingCount: number | null;
  stagingCount: number;
  stagingStale: boolean;
  canTransform: boolean;
  canUndo: boolean;
  canRedo: boolean;
  canCancelProcessing: boolean;
  canRetrySegmentation: boolean;
  canRegenerateStaging: boolean;
  stageStatus: string | null;
  /** The single next action already has a button. Do not repeat it here. */
  suppressedIds?: readonly string[];
  /** Refinement tooth toolbar already owns move, rotate, and target. */
  manipulationOwnedByToothToolbar?: boolean;
}

export interface ToolbarResolution {
  context: ToolbarContextId;
  primary: ToolbarAction[];
  more: ToolbarAction[];
  withheld: ToolbarAction[];
}

const PRIORITY_CATEGORY: Record<ActionCategory, ActionPriority> = {
  workflow: 1,
  selection: 2,
  manipulation: 3,
  viewport: 4,
  review: 5,
  utility: 6,
  advanced: 7,
};

export function commandIdForShortcut(shortcut: WorkspaceShortcut): string | null {
  switch (shortcut) {
    case "clear":
      return "clear-selection";
    case "fit-selection":
      return "fit-selection";
    case "fit-case":
      return "fit-case";
    case "arch-upper":
      return "arch-upper";
    case "arch-lower":
      return "arch-lower";
    case "arch-both":
      return "arch-both";
    case "undo":
      return "undo";
    case "redo":
      return "redo";
    case "delete":
      return null;
    default:
      return null;
  }
}

export function shortcutUsesToolbarCommand(shortcut: WorkspaceShortcut): boolean {
  const id = commandIdForShortcut(shortcut);
  return id !== null && id !== "clear-selection";
}

export function resolveToolbarContext(input: ToolbarMachineInput): ToolbarContextId {
  const stage = (input.stageStatus ?? "").toUpperCase();
  if (stage === "PROCESSING") return "processing";
  if (input.segmentationKind === "blocked_by_environment") return "blocked";
  if (stage === "FAILED" || input.segmentationKind === "failed") return "failed";
  if (
    (stage === "STALE" || (input.stagingStale && input.workspace === "staging")) &&
    !(input.sceneAvailable && input.selectionCount > 0)
  ) {
    return "stale";
  }
  if (input.segmentationKind === "not_available") return "unavailable";
  if (input.selectionCount === 1 && input.sceneAvailable) return "one-tooth";
  if (input.selectionCount > 1 && input.sceneAvailable) return "multi-tooth";
  switch (input.workspace) {
    case "analysis":
      return "segmentation-review";
    case "treatment-setup":
      return "treatment-setup";
    case "staging":
      return "staging";
    case "refinement":
      return "refinement";
    case "validation":
      return "validation";
    case "production":
      return "production";
    case "case-intake":
      return input.hasCase ? "case" : "idle";
    default:
      return input.hasCase ? "case" : "idle";
  }
}

function action(
  partial: Omit<ToolbarAction, "priority" | "destructive" | "executable" | "placement" | "truthDependency"> & {
    priority?: ActionPriority;
    truthDependency?: string | null;
    placement?: ToolbarAction["placement"];
  },
): ToolbarAction {
  const availability = partial.availability;
  const executable = availability === "available" || availability === "requires_review" || availability === "stale";
  const priority = partial.priority ?? PRIORITY_CATEGORY[partial.category];
  let placement = partial.placement;
  if (!placement) {
    if (!executable) placement = "withheld";
    else if (priority >= 6) placement = "more";
    else placement = "primary";
  }
  if (!executable) placement = "withheld";
  return {
    ...partial,
    priority,
    destructive: false,
    truthDependency: partial.truthDependency ?? null,
    executable,
    placement,
  };
}

function labelText(mode: ToolbarMachineInput["labelMode"]): string {
  if (mode === "off") return "Labels off";
  if (mode === "selected") return "Labels: selected";
  if (mode === "arch") return "Labels: arch";
  return "Labels: all";
}

export function resolveToolbar(input: ToolbarMachineInput): ToolbarResolution {
  const context = resolveToolbarContext(input);
  const suppressed = new Set(input.suppressedIds ?? []);
  const items: ToolbarAction[] = [];
  const push = (item: ToolbarAction) => {
    if (suppressed.has(item.id)) return;
    items.push(item);
  };

  const reviewTruth =
    input.segmentationKind === "fixture_test_only" || input.segmentationKind === "requires_review"
      ? "requires_review"
      : "available";

  if (context === "processing") {
    if (input.canCancelProcessing) {
      push(
        action({
          id: "cancel-processing",
          label: "Cancel processing",
          category: "workflow",
          availability: "available",
          reason: "Stops the current job. Source scans stay imported. A later run is a new job.",
          effect: "job",
          reversible: false,
          truthDependency: "processing",
        }),
      );
    }
    return pack(context, items);
  }

  if (context === "blocked") {
    push(
      action({
        id: "retry-segmentation",
        label: "Retry segmentation",
        category: "workflow",
        availability: "blocked",
        reason: "The host runtime is blocked. This is an environment blocker, not a model failure. Retry stays unavailable until that blocker is gone.",
        effect: "job",
        reversible: false,
        truthDependency: "blocked_by_environment",
      }),
    );
  } else if (context === "failed" && input.canRetrySegmentation) {
    push(
      action({
        id: "retry-segmentation",
        label: "Retry segmentation",
        category: "workflow",
        availability: "available",
        reason: "Starts a new segmentation job. The previous failure text stays until that job returns.",
        effect: "job",
        reversible: false,
        truthDependency: "failed",
      }),
    );
  } else if (
    input.canRegenerateStaging &&
    (context === "stale" || input.stagingStale) &&
    (context === "stale" || input.workspace === "staging" || input.workspace === "refinement")
  ) {
    push(
      action({
        id: "regenerate-staging",
        label: "Generate / Regenerate Staging",
        category: "workflow",
        availability: "stale",
        reason: "Staging is stale relative to the current setup. Regenerating replaces it only when the job completes.",
        effect: "job",
        reversible: false,
        truthDependency: "stale",
      }),
    );
  } else if (context === "unavailable") {
    push(
      action({
        id: "measure",
        label: "Measure",
        category: "review",
        availability: "unavailable",
        reason: "No measurement tool is active. Distances are not invented.",
        effect: "view",
        reversible: true,
      }),
    );
  }

  if (input.sceneAvailable) {
    push(
      action({
        id: "fit-case",
        label: "Fit case",
        category: "viewport",
        availability: "available",
        reason: "Frame the full case. Shortcut Home.",
        shortcut: "Home",
        effect: "view",
        reversible: true,
      }),
    );
    push(
      action({
        id: "fit-arch",
        label: "Fit arch",
        category: "viewport",
        availability: "available",
        reason: "Frame the active arch filter.",
        effect: "view",
        reversible: true,
      }),
    );
    for (const preset of [
      ["view-occlusal", "Occlusal", "Standard occlusal view."],
      ["view-front", "Front", "Standard frontal view."],
      ["view-lateral", "Lateral", "Standard right lateral view."],
    ] as const) {
      push(
        action({
          id: preset[0],
          label: preset[1],
          category: input.selectionCount > 0 ? "utility" : "viewport",
          availability: "available",
          reason: preset[2],
          effect: "view",
          reversible: true,
        }),
      );
    }
    push(
      action({
        id: "arch-upper",
        label: "Upper",
        category: "viewport",
        availability: "available",
        reason: "Show the upper arch. Shortcut 1.",
        shortcut: "1",
        effect: "view",
        reversible: true,
        active: input.archMode === "upper",
      }),
    );
    push(
      action({
        id: "arch-lower",
        label: "Lower",
        category: "viewport",
        availability: "available",
        reason: "Show the lower arch. Shortcut 2.",
        shortcut: "2",
        effect: "view",
        reversible: true,
        active: input.archMode === "lower",
      }),
    );
    push(
      action({
        id: "arch-both",
        label: "Both",
        category: "viewport",
        availability: "available",
        reason: "Show both arches. Shortcut 0.",
        shortcut: "0",
        effect: "view",
        reversible: true,
        active: input.archMode === "both",
      }),
    );
    push(
      action({
        id: "labels",
        label: labelText(input.labelMode),
        category: "review",
        availability: reviewTruth === "requires_review" ? "requires_review" : "available",
        reason: "Cycle label density. tooth_ref is shown unless FDI is authoritative. Shortcut is not assigned.",
        effect: "view",
        reversible: true,
        active: input.labelMode !== "off",
        truthDependency: input.segmentationKind,
      }),
    );
    push(
      action({
        id: "reset-view",
        label: "Reset view",
        category: "utility",
        availability: "available",
        reason: "Fit the case. Ordinary selection does not move the camera.",
        effect: "view",
        reversible: true,
      }),
    );
    push(
      action({
        id: "gingiva",
        label: "Gingiva",
        category: "advanced",
        availability: "available",
        reason: "Presentation-only gingiva. It is not clinical anatomy and does not enter calculations.",
        effect: "view",
        reversible: true,
        active: input.gingivaVisible,
        truthDependency: "presentation-only",
      }),
    );
    push(
      action({
        id: "segmentation",
        label: "Teeth",
        category: "advanced",
        availability: "available",
        reason: "Show or hide segmented tooth surfaces. This does not change identity.",
        effect: "view",
        reversible: true,
        active: input.segmentationVisible,
      }),
    );
    push(
      action({
        id: "wireframe",
        label: "Wireframe",
        category: "advanced",
        availability: "available",
        reason: "Presentation wireframe. It does not change clinical geometry.",
        effect: "view",
        reversible: true,
        active: input.wireframe,
      }),
    );
  }

  if ((context === "one-tooth" || context === "multi-tooth") && input.sceneAvailable) {
    push(
      action({
        id: "fit-selection",
        label: "Fit selection",
        category: "selection",
        availability: "available",
        reason:
          context === "one-tooth"
            ? "Frame the selected tooth_ref. Shortcut F."
            : "Frame the selected tooth set. Shortcut F.",
        shortcut: "F",
        effect: "view",
        reversible: true,
      }),
    );
  }

  if (context === "one-tooth" && input.sceneAvailable) {
    push(
      action({
        id: "isolate",
        label: "Isolate",
        category: "selection",
        availability: "available",
        reason: "Show only the selected tooth. Neighbors return when isolate is turned off.",
        effect: "view",
        reversible: true,
        active: input.isolateActive,
      }),
    );
  }

  if (context === "multi-tooth" && input.groupIdentity === "mixed") {
    push(
      action({
        id: "group-numbering",
        label: "Group numbering",
        category: "selection",
        availability: "unavailable",
        reason: "Selected teeth do not share one identity state. No group numbering action exists.",
        effect: "selection",
        reversible: true,
      }),
    );
  }

  const showTarget =
    input.targetGeometryExists &&
    !input.manipulationOwnedByToothToolbar &&
    (input.workspace === "treatment-setup" || input.workspace === "staging" || input.workspace === "refinement");

  if (showTarget) {
    push(
      action({
        id: "target",
        label: "Target",
        category: "review",
        availability: "available",
        reason: "Show the stored treatment target beside current geometry. This does not approve the plan.",
        effect: "view",
        reversible: true,
        active: input.targetVisible,
        truthDependency: "stored-target",
      }),
    );
    push(
      action({
        id: "movement",
        label: "Movement",
        category: "review",
        availability: "available",
        reason: "Show or hide remaining-movement lines. Lines are not a clinical recommendation.",
        effect: "view",
        reversible: true,
        active: input.movementVisible,
      }),
    );
  } else if (!input.targetGeometryExists) {
    push(
      action({
        id: "target",
        label: "Current / target",
        category: "review",
        availability: "unavailable",
        reason: "No treatment target is stored for this case.",
        effect: "view",
        reversible: true,
      }),
    );
  }

  if (input.workspace === "refinement") {
    push(
      action({
        id: "move",
        label: "Move / transform",
        category: "manipulation",
        availability: "unavailable",
        reason: input.manipulationOwnedByToothToolbar
          ? "Move and rotate are on the selected-tooth controls. They use the existing edit stack."
          : "Select a transformable tooth in Refinement. Move is not a separate clinical engine.",
        effect: "durable-edit",
        reversible: true,
        truthDependency: "refinement-edit",
      }),
    );
  } else {
    push(
      action({
        id: "move",
        label: "Move / transform",
        category: "manipulation",
        availability: "unavailable",
        reason: "Move is available in Refinement when a transformable tooth is selected.",
        effect: "durable-edit",
        reversible: true,
      }),
    );
  }

  if (input.workspace === "refinement" && input.canUndo) {
    push(
      action({
        id: "undo",
        label: "Undo",
        category: "manipulation",
        availability: "available",
        reason: "Undo the last durable edit. Shortcut Ctrl or Command Z.",
        shortcut: "Ctrl+Z",
        effect: "durable-edit",
        reversible: true,
      }),
    );
  }
  if (input.workspace === "refinement" && input.canRedo) {
    push(
      action({
        id: "redo",
        label: "Redo",
        category: "manipulation",
        availability: "available",
        reason: "Redo the last durable edit. Shortcut Ctrl or Command Shift Z.",
        shortcut: "Ctrl+Shift+Z",
        effect: "durable-edit",
        reversible: true,
      }),
    );
  }

  if (input.workspace === "validation") {
    push(
      action({
        id: "validation-overlay",
        label: "Validation overlay",
        category: "review",
        availability: "unavailable",
        reason: input.validationAvailable
          ? "Findings stay in the validation step. The viewport does not paint a pass, a score, or an approval."
          : "Validation findings are not available yet. Absence is not a pass.",
        effect: "view",
        reversible: true,
        truthDependency: "validation",
      }),
    );
  }

  push(
    action({
      id: "measure",
      label: "Measure",
      category: "review",
      availability: "unavailable",
      reason: "No measurement tool is active. Distances are not invented.",
      effect: "view",
      reversible: true,
    }),
  );

  if (context === "blocked" || input.segmentationKind === "blocked_by_environment" || input.segmentationKind === "not_run" || input.segmentationKind === "not_available" || input.segmentationKind === "failed") {
    push(
      action({
        id: "segmentation-correction",
        label: "Segmentation correction",
        category: "manipulation",
        availability: input.segmentationKind === "blocked_by_environment" ? "blocked" : "unavailable",
        reason:
          input.segmentationKind === "blocked_by_environment"
            ? "Boundary edit, split, merge, and identity correction stay blocked with the runtime. This is not a model failure."
            : "Boundary edit, split, merge, and identity correction are not implemented.",
        effect: "durable-edit",
        reversible: true,
      }),
    );
  }

  return pack(context, dedupe(items));
}

function dedupe(items: ToolbarAction[]): ToolbarAction[] {
  const seen = new Set<string>();
  const next: ToolbarAction[] = [];
  for (const item of items) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    next.push(item);
  }
  return next;
}

function pack(context: ToolbarContextId, items: ToolbarAction[]): ToolbarResolution {
  const ordered = [...items].sort((a, b) => a.priority - b.priority);
  return {
    context,
    primary: ordered.filter((item) => item.placement === "primary"),
    more: ordered.filter((item) => item.placement === "more"),
    withheld: ordered.filter((item) => item.placement === "withheld"),
  };
}

/** Viewport commands never write treatment state. */
export function viewportCommandMutatesClinicalState(actionId: string): boolean {
  return actionId === "undo" || actionId === "redo";
}

export function viewportOccupancy(input: {
  width: number;
  height: number;
  primaryToolCount: number;
  widgetCount: number;
}): { viewportDominant: boolean; widgetCountWithinCap: boolean; primaryToolsWithinCap: boolean } {
  const rail = input.width <= 1440 ? 216 : 240;
  const inspector = input.width <= 1440 ? 248 : 280;
  const pad = input.width <= 1440 ? 12 : 20;
  const viewport = Math.max(0, input.width - rail - inspector - pad);
  return {
    viewportDominant: viewport > rail && viewport > inspector && input.height >= 700,
    widgetCountWithinCap: input.widgetCount <= 2,
    primaryToolsWithinCap: input.primaryToolCount <= 14,
  };
}
