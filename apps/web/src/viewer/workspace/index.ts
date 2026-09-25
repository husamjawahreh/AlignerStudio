export {
  createDefaultLayerControls,
  createCadWorkspaceLayerRegistry,
  filterTeethByArchVisibility,
} from "./archLayers";
export type { ArchVisibility, WorkspaceLayerControls } from "./archLayers";

export {
  semanticIdentityFromTooth,
  selectionStateFromIdentity,
  preserveSelectionAcrossTeeth,
  identitiesEqual,
} from "./selectionIdentity";
export type { SemanticToothIdentity } from "./selectionIdentity";

export {
  CAMERA_PRESETS,
  ORIENTATION_CUBE_FACES,
  describeFitRequest,
} from "./cameraNavigation";
export type { CameraPreset, CameraPresetId, FitRequest, FitTarget, OrientationCubeFace } from "./cameraNavigation";

export { WORKSPACE_OVERLAY_CAPABILITIES, overlayCapability } from "./overlayArchitecture";
export type { OverlayCapability, OverlayKind } from "./overlayArchitecture";

export {
  pickToothFromPointer,
  prepareMeshForPicking,
  disposeMeshBoundsTree,
  enableBvhAcceleration,
  tryEnableBvhAcceleration,
  isBvhAccelerationEnabled,
} from "./picking";
export type { PickingHit, PickerOptions } from "./picking";

export {
  validateGeometryWorkerRequest,
  GEOMETRY_WORKER_FORBIDDEN_FIELDS,
} from "./geometryWorkers";
export type {
  GeometryWorkerOperation,
  GeometryWorkerRequest,
  GeometryWorkerResponse,
} from "./geometryWorkers";

export { createCaseSceneHierarchy, setArchGroupVisibility } from "./sceneHierarchy";
export type { CaseSceneHierarchy } from "./sceneHierarchy";

export { resolveToothVisualRole, toothVisualStyle } from "./selectionVisuals";
export type { ToothVisualInput, ToothVisualRole, ToothVisualStyle } from "./selectionVisuals";

export {
  resolveFitBounds,
  computeObjectBounds,
  cameraPositionForSphere,
  nearFarForSphere,
} from "./fitTargets";
export type { FitBoundsResult } from "./fitTargets";

export {
  createOverlayRegistry,
  capabilityOverlays,
  isClinicalGeometryOverlay,
} from "./overlayRegistry";
export type { OverlayRegistration, OverlayRegistry, OverlaySource } from "./overlayRegistry";

export { disposeObjectTree, disposeMeshResources, rendererResourceSnapshot } from "./resourceDisposal";
