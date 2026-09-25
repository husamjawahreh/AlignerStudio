/**
 * Camera navigation / orientation-cube / fit architecture.
 * Foundation only — StageViewer may adopt these helpers incrementally.
 */

export type CameraPresetId =
  | "occlusal"
  | "front"
  | "back"
  | "left"
  | "right"
  | "upper"
  | "lower";

export type FitTarget = "selected" | "arch" | "case";

export interface CameraPreset {
  id: CameraPresetId;
  label: string;
  /** Unit direction looking toward the origin. */
  direction: readonly [number, number, number];
}

export const CAMERA_PRESETS: readonly CameraPreset[] = [
  { id: "occlusal", label: "Occlusal", direction: [0, 1, 0.01] },
  { id: "front", label: "Front", direction: [0, 0.08, 1] },
  { id: "back", label: "Back", direction: [0, 0.08, -1] },
  { id: "left", label: "Left", direction: [-1, 0.08, 0] },
  { id: "right", label: "Right", direction: [1, 0.08, 0] },
  { id: "upper", label: "Upper", direction: [0, 1, 0] },
  { id: "lower", label: "Lower", direction: [0, -1, 0] },
] as const;

export interface OrientationCubeFace {
  id: CameraPresetId;
  label: string;
}

/** Orientation-cube face map — UI chrome only; does not alter clinical coordinates. */
export const ORIENTATION_CUBE_FACES: readonly OrientationCubeFace[] = [
  { id: "front", label: "F" },
  { id: "back", label: "B" },
  { id: "left", label: "L" },
  { id: "right", label: "R" },
  { id: "upper", label: "U" },
  { id: "lower", label: "Lo" },
];

export interface FitRequest {
  target: FitTarget;
  arch?: "upper" | "lower";
  selectedKey?: string | null;
  /** Semantic keys. Fit selection uses these instead of a mesh index. */
  selectedKeys?: readonly string[];
}

export function describeFitRequest(request: FitRequest): string {
  if (request.target === "selected") return "Fit selected tooth";
  if (request.target === "arch") return `Fit ${request.arch ?? "arch"}`;
  return "Fit case";
}
