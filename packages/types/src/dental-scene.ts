import type { DataProvenance } from "@alignerstudio/contracts";

export type DentalArch = "upper" | "lower";

export type SceneLayerId =
  | "original-scan"
  | "gingiva-base"
  | "upper-teeth"
  | "lower-teeth"
  | "segmentation"
  | "proposed-setup"
  | "current-stage"
  | "ipr"
  | "contacts"
  | "collisions"
  | "attachments"
  | "movement-vectors"
  | "tooth-labels"
  | "measurements";

export interface SceneLayerState {
  id: SceneLayerId;
  label: string;
  visible: boolean;
  available: boolean;
  reason?: string;
}

export type SceneLayerRegistry = Readonly<Record<SceneLayerId, SceneLayerState>>;

export interface DentalToothMesh {
  instanceId: number;
  toothRef?: string | null;
  semanticIdentifier?: number | null;
  fdiNumber?: number | null;
  arch: DentalArch;
  vertices: readonly [number, number, number][];
  faces: readonly [number, number, number][];
  centroid?: readonly [number, number, number];
  confidence?: number | null;
  provenance: DataProvenance;
  fixture: boolean;
  experimental?: boolean;
}

export interface DentalScene {
  originalScans: Readonly<Record<DentalArch, DentalToothMesh[]>>;
  segmentedTeeth: Readonly<Record<DentalArch, DentalToothMesh[]>>;
  gingivaBase?: DentalToothMesh[];
  proposedSetup?: DentalToothMesh[];
  currentStage?: TreatmentStage;
  overlays: Readonly<Record<string, readonly DentalToothMesh[]>>;
  layers: SceneLayerRegistry;
  provenance: DataProvenance;
  fixture: boolean;
  experimental?: boolean;
}

export interface ToothSelectionState {
  selectedToothRef: string | null;
  semanticIdentifier: number | null;
  fdiNumber: number | null;
  arch: DentalArch | null;
  confidence: number | null;
}

export interface ToothMovementState {
  translationX: number;
  translationY: number;
  translationZ: number;
  rotationX: number;
  rotationY: number;
  rotationZ: number;
  tip: number;
  torque: number;
  intrusion: number;
  extrusion: number;
  locked: boolean;
  excluded: boolean;
}

export interface TreatmentStage {
  id: string;
  index: number;
  label: string;
  type: "initial" | "intermediate" | "target" | "review";
  toothMovements: Readonly<Record<string, ToothMovementState>>;
  validations: readonly string[];
  metadata: Readonly<Record<string, string | number | boolean>>;
}

export interface PlanningEngineAdapter {
  readonly name: string;
  createPlan(input: unknown): Promise<unknown>;
}

export interface LandmarkEngineAdapter {
  readonly name: string;
  detectLandmarks(input: unknown): Promise<unknown>;
}

export interface GeometryEngineBoundary {
  parseMesh(input: unknown): Promise<unknown>;
  repairMesh?(input: unknown): Promise<unknown>;
  querySpatialIndex?(input: unknown): Promise<unknown>;
  detectCollisions?(input: unknown): Promise<unknown>;
  booleanOperation?(input: unknown): Promise<unknown>;
}

export const DENTAL_SCENE_LAYER_LABELS: Readonly<Record<SceneLayerId, string>> = {
  "original-scan": "Original Scan",
  "gingiva-base": "Gingiva",
  "upper-teeth": "Upper Teeth",
  "lower-teeth": "Lower Teeth",
  segmentation: "Segmentation",
  "proposed-setup": "Proposed Setup",
  "current-stage": "Current Stage",
  ipr: "IPR",
  contacts: "Contacts",
  collisions: "Collisions",
  attachments: "Attachments",
  "movement-vectors": "Movement Vectors",
  "tooth-labels": "Tooth Labels",
  measurements: "Measurements",
};

export function createSceneLayerRegistry(
  overrides: Partial<Record<SceneLayerId, Partial<SceneLayerState>>> = {},
): SceneLayerRegistry {
  const layerIds = Object.keys(DENTAL_SCENE_LAYER_LABELS) as SceneLayerId[];
  return Object.fromEntries(
    layerIds.map((id) => [
      id,
      {
        id,
        label: DENTAL_SCENE_LAYER_LABELS[id],
        visible: id === "upper-teeth" || id === "lower-teeth" || id === "current-stage",
        available: false,
        ...overrides[id],
      },
    ]),
  ) as SceneLayerRegistry;
}