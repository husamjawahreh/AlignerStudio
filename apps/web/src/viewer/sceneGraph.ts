import type { SceneLayerRegistry } from "@alignerstudio/types";
import type { ReviewStage } from "../review/types";

export type SceneArch = "upper" | "lower";

export interface DentalSceneGraph {
  originalScans: Partial<Record<SceneArch, ArrayBuffer>>;
  segmentedStage: ReviewStage;
  layers: SceneLayerRegistry;
}

export function createDentalSceneGraph(
  segmentedStage: ReviewStage,
  originalScans: Partial<Record<SceneArch, ArrayBuffer>>,
  layers: SceneLayerRegistry,
): DentalSceneGraph {
  return { originalScans, segmentedStage, layers };
}
