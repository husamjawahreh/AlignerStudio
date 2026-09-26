/**
 * Overlay architecture for clipping, measurement, validation, local frames, gizmos.
 * Declares capabilities with honest availability — no fake clinical overlays.
 */

export type OverlayKind =
  | "clipping"
  | "section"
  | "measurement"
  | "validation"
  | "local_frames"
  | "gizmo"
  | "orientation_cube";

export interface OverlayCapability {
  kind: OverlayKind;
  label: string;
  available: boolean;
  reason: string;
}

export const WORKSPACE_OVERLAY_CAPABILITIES: readonly OverlayCapability[] = [
  {
    kind: "clipping",
    label: "Clipping planes",
    available: false,
    reason: "Clipping architecture is reserved; interactive clipping is not implemented yet.",
  },
  {
    kind: "section",
    label: "Section view",
    available: false,
    reason: "Section architecture is reserved; section tools are not implemented yet.",
  },
  {
    kind: "measurement",
    label: "Measurements",
    available: false,
    reason: "Measurement overlays are not implemented yet.",
  },
  {
    kind: "validation",
    label: "Validation overlays",
    available: false,
    reason: "Validation findings are listed in panels; 3D validation overlays are not implemented yet.",
  },
  {
    kind: "local_frames",
    label: "Local coordinate frames",
    available: false,
    reason: "Local-axis visualization architecture is reserved for later First Version work.",
  },
  {
    kind: "gizmo",
    label: "Movement gizmo",
    available: true,
    reason: "Translate/rotate gizmo is available when a tooth is selected and treatment exists.",
  },
  {
    kind: "orientation_cube",
    label: "Orientation cube",
    available: true,
    reason: "Standard view presets are available from the viewport toolbar (orientation-cube chrome is optional).",
  },
] as const;

export type OverlayFindingSeverity =
  | "fail"
  | "warning"
  | "requires_review"
  | "stale"
  | "unavailable"
  | "absent";

export interface OverlayDrawDecision {
  draw: boolean;
  /** An absent overlay is never a pass, a score, or clinical approval. */
  impliesApproval: false;
  tone: "none" | "fail" | "warning" | "review" | "stale";
  reason: string;
}

/**
 * Decide whether a validation mark may be drawn.
 * Does not score, approve, or invent a finding.
 */
export function validationOverlayPresentation(input: {
  capabilityAvailable: boolean;
  severity: OverlayFindingSeverity | null;
}): OverlayDrawDecision {
  if (!input.capabilityAvailable) {
    return {
      draw: false,
      impliesApproval: false,
      tone: "none",
      reason: "Validation overlay is not available. Absence is not a pass.",
    };
  }
  if (input.severity == null || input.severity === "unavailable" || input.severity === "absent") {
    return {
      draw: false,
      impliesApproval: false,
      tone: "none",
      reason: "No validation finding is stored. Nothing is drawn, and nothing is marked safe.",
    };
  }
  if (input.severity === "fail") {
    return { draw: true, impliesApproval: false, tone: "fail", reason: "Stored validation finding: fail." };
  }
  if (input.severity === "warning") {
    return {
      draw: true,
      impliesApproval: false,
      tone: "warning",
      reason: "Stored validation finding: warning.",
    };
  }
  if (input.severity === "requires_review") {
    return { draw: true, impliesApproval: false, tone: "review", reason: "Stored state requires review." };
  }
  return { draw: true, impliesApproval: false, tone: "stale", reason: "Stored validation state is stale." };
}

/** Draw a measurement only when a real measurement and a capability both exist. */
export function measurementOverlayPresentation(input: {
  capabilityAvailable: boolean;
  hasMeasurement: boolean;
  unit: string | null;
}): { draw: boolean; unitLabel: string | null; reason: string } {
  if (!input.capabilityAvailable || !input.hasMeasurement) {
    return {
      draw: false,
      unitLabel: null,
      reason: "Measurement overlay is unavailable. No dimension is invented.",
    };
  }
  const unit = input.unit?.trim() || null;
  return {
    draw: true,
    unitLabel: unit ?? "model-space units (unverified)",
    reason: unit
      ? `Measurement overlay uses ${unit}.`
      : "Measurement exists without a verified unit. The label stays model-space.",
  };
}

export function overlayCapability(kind: OverlayKind): OverlayCapability {
  const found = WORKSPACE_OVERLAY_CAPABILITIES.find((item) => item.kind === kind);
  if (!found) {
    return {
      kind,
      label: kind,
      available: false,
      reason: "Unknown overlay.",
    };
  }
  return found;
}
