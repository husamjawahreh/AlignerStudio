/**
 * Professional dental CAD workspace architecture foundation (FV-01).
 *
 * These modules define contracts and helpers for upper/lower layers, selection
 * identity, camera navigation, overlays, and picking. They do not invent FDI
 * or clinical anatomy.
 */

import type { SceneLayerId, SceneLayerRegistry, SceneLayerState } from "@alignerstudio/types";
import { createSceneLayerRegistry } from "@alignerstudio/types";
import type { ReviewToothMesh } from "../../review/types";
import { reviewToothKey } from "../toothKey";

export type ArchVisibility = Readonly<{ upper: boolean; lower: boolean }>;

export interface WorkspaceLayerControls {
  visibility: ArchVisibility;
  opacity: Partial<Record<"original" | "gingiva" | "teeth" | "ghost", number>>;
  isolatedArch: "upper" | "lower" | null;
  /** When set, only this tooth_ref remains visible (semantic identity). */
  isolatedToothKey: string | null;
}

export function createDefaultLayerControls(): WorkspaceLayerControls {
  return {
    visibility: { upper: true, lower: true },
    opacity: { original: 0.28, gingiva: 1, teeth: 1, ghost: 0.35 },
    isolatedArch: null,
    isolatedToothKey: null,
  };
}

/** Apply arch / tooth isolation without inventing teeth — only filters existing instances. */
export function filterTeethByArchVisibility(
  teeth: readonly ReviewToothMesh[],
  controls: WorkspaceLayerControls,
): ReviewToothMesh[] {
  const showUpper =
    controls.isolatedArch === "upper" || (controls.isolatedArch === null && controls.visibility.upper);
  const showLower =
    controls.isolatedArch === "lower" || (controls.isolatedArch === null && controls.visibility.lower);
  return teeth.filter((tooth) => {
    if (tooth.arch === "upper" ? !showUpper : !showLower) return false;
    if (controls.isolatedToothKey) {
      return reviewToothKey(tooth) === controls.isolatedToothKey;
    }
    return true;
  });
}

/** Layer registry with honest availability for overlays not yet implemented. */
export function createCadWorkspaceLayerRegistry(
  overrides: Partial<Record<SceneLayerId, Partial<SceneLayerState>>> = {},
): SceneLayerRegistry {
  return createSceneLayerRegistry({
    ipr: {
      available: false,
      visible: false,
      reason: "IPR overlays are not available yet.",
    },
    contacts: {
      available: false,
      visible: false,
      reason: "Contact overlays are not available yet.",
    },
    collisions: {
      available: false,
      visible: false,
      reason: "Collision overlays are not available yet.",
    },
    attachments: {
      available: false,
      visible: false,
      reason: "Attachment overlays are not available yet.",
    },
    measurements: {
      available: false,
      visible: false,
      reason: "Measurement overlays are not available yet.",
    },
    ...overrides,
  });
}
