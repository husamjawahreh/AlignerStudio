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
