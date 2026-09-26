/**
 * 3D label density. Presentation only.
 * Labels never invent FDI — callers pass toothReviewLabel text.
 */

export type ToothLabelMode = "selected" | "arch" | "all" | "off";

export const LABEL_MODE_CYCLE: readonly ToothLabelMode[] = ["selected", "arch", "all", "off"];

/** Above this count, non-priority labels stay hidden so anatomy remains readable. */
export const LABEL_DENSITY_CAP = 16;

export function nextLabelMode(mode: ToothLabelMode): ToothLabelMode {
  const index = LABEL_MODE_CYCLE.indexOf(mode);
  const next = LABEL_MODE_CYCLE[(index + 1) % LABEL_MODE_CYCLE.length];
  return next ?? "selected";
}

export function resolveLabelVisibility(input: {
  mode: ToothLabelMode;
  selected: boolean;
  hovered: boolean;
  multiSelected: boolean;
  singleArchIsolated: boolean;
  visibleToothCount: number;
}): boolean {
  if (input.mode === "off") return false;
  if (input.selected || input.hovered || input.multiSelected) return true;
  if (input.visibleToothCount > LABEL_DENSITY_CAP) return false;
  if (input.mode === "all") return true;
  if (input.mode === "arch") return input.singleArchIsolated;
  return false;
}
