/**
 * Wave 5 presentation helpers.
 * Priority, disclosure, and copy only. No clinical computation.
 */

import type { ToolItem } from "./model";
import type { NextAction } from "./nextAction";

/** Viewport tools that stay one click away. The rest sit under More. */
const VISIBLE_TOOL_IDS = new Set([
  "fit-selection",
  "isolate",
  "fit-case",
  "fit-arch",
  "arch-upper",
  "arch-lower",
  "arch-both",
  "view-occlusal",
  "view-front",
  "view-lateral",
  "labels",
  "target",
  "movement",
]);

const TOOL_ORDER = [
  "fit-selection",
  "isolate",
  "fit-case",
  "fit-arch",
  "arch-upper",
  "arch-lower",
  "arch-both",
  "view-occlusal",
  "view-front",
  "view-lateral",
  "labels",
  "target",
  "movement",
  "reset-view",
  "gingiva",
  "segmentation",
  "wireframe",
];

export function splitToolbar(tools: readonly ToolItem[]): {
  visible: ToolItem[];
  advanced: ToolItem[];
} {
  const visible: ToolItem[] = [];
  const advanced: ToolItem[] = [];
  for (const tool of tools) {
    if (VISIBLE_TOOL_IDS.has(tool.id)) visible.push(tool);
    else advanced.push(tool);
  }
  const rank = (id: string) => {
    const index = TOOL_ORDER.indexOf(id);
    return index === -1 ? TOOL_ORDER.length : index;
  };
  visible.sort((a, b) => rank(a.id) - rank(b.id));
  advanced.sort((a, b) => rank(a.id) - rank(b.id));
  return { visible, advanced };
}

/** Drop a notice that repeats the primary status sentence. */
export function dedupeNotice(primary: string | null | undefined, notice: string | null | undefined): string | null {
  const next = notice?.trim() ?? "";
  if (!next) return null;
  const current = primary?.trim() ?? "";
  if (current && current === next) return null;
  return next;
}

export type TruthVisual =
  | "verified"
  | "computed"
  | "requires_review"
  | "not_available"
  | "blocked_by_environment"
  | "failed"
  | "stale"
  | "cancelled"
  | "interrupted"
  | "fixture";

/**
 * Truth color is never a clinical approval.
 * Missing, blocked, fixture, and unavailable states do not read as safe.
 */
export function truthImpliesClinicalApproval(state: TruthVisual): false {
  void state;
  return false;
}

export function workflowOrientation(input: {
  stepLabel: string;
  blockReason: string | null;
  next: NextAction | null;
}): { where: string; now: string; next: string } {
  return {
    where: input.stepLabel,
    now: input.blockReason ?? "This step can be used with the evidence loaded so far.",
    next: input.next
      ? `${input.next.label}. ${input.next.reason}`
      : "No further action is available from the current evidence.",
  };
}

export function stepVisual(input: {
  status: string;
  environmentBlocked: boolean;
}): "current" | "complete" | "ready" | "blocked" | "unavailable" | "environment" {
  if (input.environmentBlocked) return "environment";
  if (input.status === "current") return "current";
  if (input.status === "complete") return "complete";
  if (input.status === "blocked") return "blocked";
  if (input.status === "ready") return "ready";
  return "unavailable";
}
