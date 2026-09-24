import type { SceneLayerRegistry } from "@alignerstudio/types";
import type { ReviewStage } from "../review/types";
import type { RealGingivaMeshInput } from "./syntheticGingiva";

export type SceneArch = "upper" | "lower";

export interface DentalSceneGraph {
  originalScans: Partial<Record<SceneArch, ArrayBuffer>>;
  segmentedStage: ReviewStage;
  layers: SceneLayerRegistry;
  /**
   * Optional real gingival meshes from case/pipeline data.
   * Consumed only for viewport presentation when usable.
   */
  realGingiva?: readonly RealGingivaMeshInput[];
}

export function createDentalSceneGraph(
  segmentedStage: ReviewStage,
  originalScans: Partial<Record<SceneArch, ArrayBuffer>>,
  layers: SceneLayerRegistry,
  realGingiva?: readonly RealGingivaMeshInput[],
): DentalSceneGraph {
  return {
    originalScans,
    segmentedStage,
    layers,
    ...(realGingiva && realGingiva.length > 0 ? { realGingiva } : {}),
  };
}
