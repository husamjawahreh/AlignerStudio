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
