import { useEffect, useRef, type ReactNode } from "react";
import * as THREE from "three";
import type { SceneLayerRegistry } from "@alignerstudio/types";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { TransformControls } from "three/examples/jsm/controls/TransformControls.js";
import type { ReviewStage, ReviewToothMesh } from "../review/types";
import type { MovementSummary } from "../review/types";
import type { DentalSceneGraph } from "./sceneGraph";
import {
  dentalMaterialProfiles,
  enamelProfileForArch,
  profileColor,
} from "./materialProfiles";
import {
  findMatchingTooth,
  remainingMovementEndpoints,
  toothDisplayCentroid,
} from "./movementPresentation";
import { resolveGingivaPresentation } from "./syntheticGingiva";
import { reviewToothKey, toothMatchesKey } from "./toothKey";
import { float32PositionsFromVertices, uint32IndicesFromFaces } from "./geometryBuffers";
import {
  CAMERA_PRESETS,
  type CameraPresetId,
  type FitRequest,
  createCaseSceneHierarchy,
  enableBvhAcceleration,
  prepareMeshForPicking,
  pickToothFromPointer,
  resolveFitBounds,
  cameraPositionForSphere,
  nearFarForSphere,
  disposeObjectTree,
  toothVisualStyle,
  setArchGroupVisibility,
} from "./workspace";

interface StageViewerProps {
  stage?: ReviewStage;
  sceneGraph: DentalSceneGraph;
  /** Final/target stage for ghost overlay and remaining-movement vectors. */
  targetStage?: ReviewStage | null;
  selectedTooth: string | null;
  /** Multi-selection foundation — additional semantic keys. */
  multiSelectedTeeth?: readonly string[];
  showUpper: boolean;
  showLower: boolean;
  /** Semantic arch isolation — null means use showUpper/showLower. */
  isolatedArch?: "upper" | "lower" | null;
  /** Isolate a single tooth by semantic key. */
  isolatedToothKey?: string | null;
  showOriginal: boolean;
  originalOpacity: number;
  wireframe: boolean;
  hiddenToothIds: ReadonlySet<number>;
  onSelectTooth: (toothRef: string) => void;
  onClearSelection?: () => void;
  onFit: () => void;
  onReset: () => void;
  gizmoMode?: "translate" | "rotate";
  onGizmoMovement?: (movement: MovementSummary) => void;
  /** When false, gizmo detaches — locked/excluded/unavailable teeth stay inspectable. */
  transformEnabled?: boolean;
  /** Selection-scoped controls rendered above the camera toolbar. */
  contextualToolbar?: ReactNode;
}

interface ToothRecord {
  mesh: THREE.Mesh;
  material: THREE.MeshStandardMaterial;
  label: HTMLDivElement;
  tooth: ReviewToothMesh;
  toothKey: string;
  colorTarget: THREE.Color;
  emissiveTarget: THREE.Color;
  emissiveIntensityTarget: number;
  opacityTarget: number;
}

const SCENE_BG = 0x06090d;
const CAMERA_TRANSITION_MS = 480;
const SELECTION_LERP = 0.18;

const PRESET_DIRECTIONS: Record<CameraPresetId, THREE.Vector3> = Object.fromEntries(
  CAMERA_PRESETS.map((preset) => [
    preset.id,
    new THREE.Vector3(...preset.direction),
  ]),
) as Record<CameraPresetId, THREE.Vector3>;

export function StageViewer({
  sceneGraph,
  targetStage = null,
  selectedTooth,
  multiSelectedTeeth = [],
  showUpper,
  showLower,
  isolatedArch = null,
  isolatedToothKey = null,
  showOriginal,
  originalOpacity,
  wireframe,
  hiddenToothIds,
  onSelectTooth,
  onClearSelection,
  onFit,
  onReset,
  gizmoMode = "translate",
  onGizmoMovement,
  transformEnabled = true,
  contextualToolbar,
}: StageViewerProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
  const fitRef = useRef<((request?: FitRequest) => void) | null>(null);
  const resetRef = useRef<(() => void) | null>(null);
  const viewRef = useRef<((view: CameraPresetId) => void) | null>(null);
  const recordsRef = useRef<ToothRecord[]>([]);
  const selectRef = useRef(onSelectTooth);
  const clearSelectRef = useRef(onClearSelection);
  const gizmoRef = useRef<TransformControls | null>(null);
  const gizmoCallbackRef = useRef(onGizmoMovement);
  const ghostHighlightRef = useRef<((key: string | null) => void) | null>(null);
  const selectedToothRef = useRef(selectedTooth);
  const multiSelectedRef = useRef(multiSelectedTeeth);
  const hoveredKeyRef = useRef<string | null>(null);
  const applyVisualsRef = useRef<(() => void) | null>(null);
  const applyVisibilityRef = useRef<(() => void) | null>(null);
  /** Visibility / wireframe filters — applied without tearing down BVH meshes (WP-12). */
  const visibilityRef = useRef({
    effectiveShowUpper: true,
    effectiveShowLower: true,
    wireframe: false,
    hiddenToothIds,
    isolatedToothKey: null as string | null,
  });
  selectRef.current = onSelectTooth;
  clearSelectRef.current = onClearSelection;
  gizmoCallbackRef.current = onGizmoMovement;
  selectedToothRef.current = selectedTooth;
  multiSelectedRef.current = multiSelectedTeeth;

  const effectiveShowUpper =
    isolatedArch === "upper" || (isolatedArch === null && showUpper);
  const effectiveShowLower =
    isolatedArch === "lower" || (isolatedArch === null && showLower);
  visibilityRef.current = {
    effectiveShowUpper,
    effectiveShowLower,
    wireframe,
    hiddenToothIds,
    isolatedToothKey: isolatedToothKey ?? null,
  };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    enableBvhAcceleration();

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(SCENE_BG);
    scene.fog = new THREE.Fog(SCENE_BG, 40, 120);

    const camera = new THREE.PerspectiveCamera(42, 1, 0.05, 2000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.replaceChildren(renderer.domElement);

    const pmrem = new THREE.PMREMGenerator(renderer);
    const environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = environment;
    pmrem.dispose();

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = true;
    controls.enableZoom = true;
    const transformControls = new TransformControls(camera, renderer.domElement);
    transformControls.setMode(gizmoMode);
    transformControls.setSize(0.75);
    scene.add(transformControls);
    gizmoRef.current = transformControls;
    const handleGizmoChange = () => {
      const object = transformControls.object;
      if (!object || !gizmoCallbackRef.current) return;
      gizmoCallbackRef.current({
        translationX: object.position.x,
        translationY: object.position.y,
        translationZ: object.position.z,
        rotation: (object.rotation.y * 180) / Math.PI,
        tip: (object.rotation.x * 180) / Math.PI,
        torque: (object.rotation.z * 180) / Math.PI,
        angulation: 0,
        intrusion: 0,
        extrusion: 0,
      });
    };
    transformControls.addEventListener("objectChange", handleGizmoChange);
    const handleDragging = (event: { value: unknown }) => {
      controls.enabled = event.value !== true;
    };
    transformControls.addEventListener("dragging-changed", handleDragging);

    scene.add(new THREE.HemisphereLight(0xfff8f0, 0x0c1218, 1.05));
    const keyLight = new THREE.DirectionalLight(0xfff6ec, 2.05);
    keyLight.position.set(7, 16, 11);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(2048, 2048);
    keyLight.shadow.bias = -0.0002;
    keyLight.shadow.normalBias = 0.025;
    keyLight.shadow.radius = 4;
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xa8c4d4, 0.78);
    fillLight.position.set(-11, 6, -5);
    scene.add(fillLight);
    const rimLight = new THREE.DirectionalLight(0xe2c49a, 0.62);
    rimLight.position.set(1, 7, -15);
    scene.add(rimLight);
    const bounceLight = new THREE.DirectionalLight(0xd0d6dc, 0.34);
    bounceLight.position.set(0, -9, 5);
    scene.add(bounceLight);
    scene.background = new THREE.Color(0x0d131a);
    scene.fog = new THREE.FogExp2(0x0d131a, 0.012);

    const hierarchy = createCaseSceneHierarchy();
    scene.add(hierarchy.allContent);
    // Always build both arches; visibility filters update without BVH rebuild (WP-12).
    setArchGroupVisibility(hierarchy, "upper", true);
    setArchGroupVisibility(hierarchy, "lower", true);

    const originalObjects = new THREE.Group();
    originalObjects.name = "OriginalScans";
    hierarchy.referenceLayer.add(originalObjects);

    const presentationObjects = new THREE.Group();
    presentationObjects.name = "PresentationDepth";
    scene.add(presentationObjects);

    const raycastMeshes: THREE.Mesh[] = [];
    const labels: HTMLDivElement[] = [];
    const records: ToothRecord[] = [];
    recordsRef.current = records;
    const fitMeshIndex: Array<{ object: THREE.Object3D; toothKey: string; arch: "upper" | "lower" }> =
      [];
    const layers: SceneLayerRegistry = sceneGraph.layers;
    const stage = sceneGraph.segmentedStage;
    const targetTeeth = targetStage?.teeth ?? [];

    const toothPassesFilter = (tooth: ReviewToothMesh): boolean => {
      const filters = visibilityRef.current;
      const archVisible =
        tooth.arch === "upper" ? filters.effectiveShowUpper : filters.effectiveShowLower;
      if (!archVisible) return false;
      if (filters.hiddenToothIds.has(tooth.instanceId)) return false;
      if (filters.isolatedToothKey && reviewToothKey(tooth) !== filters.isolatedToothKey) {
        return false;
      }
      return true;
    };

    if (showOriginal && layers["original-scan"].visible) {
      const loader = new STLLoader();
      for (const arch of ["upper", "lower"] as const) {
        const buffer = sceneGraph.originalScans[arch];
        if (!buffer) continue;
        const geometry = loader.parse(buffer.slice(0));
        geometry.computeVertexNormals();
        const profile =
          arch === "upper"
            ? dentalMaterialProfiles.originalScanUpper
            : dentalMaterialProfiles.originalScanLower;
        const material = new THREE.MeshStandardMaterial({
          ...profile,
          opacity: originalOpacity,
        });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.userData.presentationOnly = true;
        mesh.userData.arch = arch;
        mesh.userData.role = "original-scan";
        originalObjects.add(mesh);
      }
    }

    // Target / proposed-setup ghost overlay (presentation only, not raycast).
    if (layers["proposed-setup"].visible && targetTeeth.length > 0) {
      for (const tooth of targetTeeth) {
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(float32PositionsFromVertices(tooth.vertices), 3),
        );
        geometry.setIndex(uint32IndicesFromFaces(tooth.faces));
        geometry.computeVertexNormals();
        const material = new THREE.MeshStandardMaterial({
          ...dentalMaterialProfiles.enamelGhost,
        });
        const mesh = new THREE.Mesh(geometry, material);
        const key = reviewToothKey(tooth);
        mesh.userData.presentationOnly = true;
        mesh.userData.role = "target-ghost";
        mesh.userData.toothRef = key;
        mesh.userData.toothKey = key;
        mesh.userData.instanceId = tooth.instanceId;
        mesh.userData.arch = tooth.arch;
        hierarchy.treatmentLayer.add(mesh);
      }
    }

    for (const tooth of stage.teeth) {
      if (!layers.segmentation.visible) continue;
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(float32PositionsFromVertices(tooth.vertices), 3),
      );
      geometry.setIndex(uint32IndicesFromFaces(tooth.faces));
      geometry.computeVertexNormals();
      const baseProfile = enamelProfileForArch(tooth.arch);
      const material = new THREE.MeshStandardMaterial({
        ...baseProfile,
        wireframe: visibilityRef.current.wireframe,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      const key = reviewToothKey(tooth);
      // Stable semantic identity on the mesh — never array index as source of truth.
      mesh.userData.toothRef = key;
      mesh.userData.toothKey = key;
      mesh.userData.instanceId = tooth.instanceId;
      mesh.userData.arch = tooth.arch;
      mesh.userData.validationStatus = tooth.validationStatus;
      prepareMeshForPicking(mesh);
      if (tooth.arch === "upper") hierarchy.upperTeeth.add(mesh);
      else hierarchy.lowerTeeth.add(mesh);
      raycastMeshes.push(mesh);
      fitMeshIndex.push({ object: mesh, toothKey: key, arch: tooth.arch });
      const label = document.createElement("div");
      label.className = `stage-tooth-label is-${tooth.arch}`;
      label.textContent = tooth.fdiNumber ? `FDI ${tooth.fdiNumber}` : `${key} · semantic`;
      label.setAttribute("data-testid", `tooth-label-${tooth.instanceId}`);
      label.setAttribute("data-tooth-key", key);
      container.appendChild(label);
      labels.push(label);
      records.push({
        mesh,
        material,
        label,
        tooth,
        toothKey: key,
        colorTarget: new THREE.Color(profileColor(baseProfile.color, 0xf2e8d4)),
        emissiveTarget: new THREE.Color(0x000000),
        emissiveIntensityTarget: 0,
        opacityTarget: 1,
      });

      if (layers["movement-vectors"].visible) {
        const target = findMatchingTooth(targetTeeth, tooth);
        const endpoints = remainingMovementEndpoints(tooth, target);
        if (endpoints) {
          const vectorGeometry = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(...endpoints.start),
            new THREE.Vector3(...endpoints.end),
          ]);
          const vector = new THREE.Line(
            vectorGeometry,
            new THREE.LineBasicMaterial({
              ...dentalMaterialProfiles.movementVector,
              linewidth: 2,
            }),
          );
          vector.userData.presentationOnly = true;
          vector.userData.role = "movement-vector";
          vector.userData.toothKey = key;
          vector.userData.instanceId = tooth.instanceId;
          vector.userData.arch = tooth.arch;
          hierarchy.treatmentLayer.add(vector);
        }
      }
    }

    if (layers["gingiva-base"].visible) {
      // Build gingiva for both arches; arch/isolate filters toggle visibility later.
      const gingivaMeshes = resolveGingivaPresentation(stage.teeth, sceneGraph.realGingiva, {
        includeUpper: layers["upper-teeth"].visible,
        includeLower: layers["lower-teeth"].visible,
        hiddenToothIds: new Set(),
      });
      for (const gingiva of gingivaMeshes) {
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(float32PositionsFromVertices(gingiva.vertices), 3),
        );
        geometry.setIndex(uint32IndicesFromFaces(gingiva.faces));
        geometry.computeVertexNormals();
        const profile =
          gingiva.source === "real"
            ? dentalMaterialProfiles.gingivaReal
            : dentalMaterialProfiles.gingivaVisualization;
        const material = new THREE.MeshStandardMaterial({ ...profile });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        mesh.userData.presentationOnly = true;
        mesh.userData.gingivaSource = gingiva.source;
        mesh.userData.arch = gingiva.arch;
        mesh.userData.role = "gingiva";
        mesh.userData.clinicalGeometry = false;
        if (gingiva.arch === "upper") hierarchy.upperGingiva.add(mesh);
        else hierarchy.lowerGingiva.add(mesh);
      }
    }

    const refreshGhostHighlight = (selectedKey: string | null) => {
      hierarchy.treatmentLayer.traverse((object) => {
        if (!(object instanceof THREE.Mesh)) return;
        if (object.userData.role !== "target-ghost") return;
        const material = object.material;
        if (!(material instanceof THREE.MeshStandardMaterial)) return;
        const selected = selectedKey != null && object.userData.toothKey === selectedKey;
        const profile = selected ? dentalMaterialProfiles.enamelTarget : dentalMaterialProfiles.enamelGhost;
        material.color.set(profileColor(profile.color, selected ? 0xf7f1e6 : 0xd5ddd9));
        material.opacity = Number(profile.opacity ?? (selected ? 0.7 : 0.2));
        material.transparent = true;
        material.depthWrite = false;
      });
    };
    refreshGhostHighlight(null);

    const shadowCatcher = new THREE.Mesh(
      new THREE.PlaneGeometry(1, 1),
      new THREE.ShadowMaterial({ opacity: 0.38, transparent: true }),
    );
    shadowCatcher.rotation.x = -Math.PI / 2;
    shadowCatcher.receiveShadow = true;
    shadowCatcher.renderOrder = -1;
    presentationObjects.add(shadowCatcher);

    const configurePresentationDepth = (sphere: THREE.Sphere, bounds: THREE.Box3) => {
      const radius = Math.max(sphere.radius, 1);
      shadowCatcher.position.set(sphere.center.x, bounds.min.y - radius * 0.02, sphere.center.z);
      shadowCatcher.scale.set(radius * 5, radius * 5, 1);
      keyLight.target.position.copy(sphere.center);
      scene.add(keyLight.target);
      const shadowExtent = radius * 2.4;
      keyLight.shadow.camera.left = -shadowExtent;
      keyLight.shadow.camera.right = shadowExtent;
      keyLight.shadow.camera.top = shadowExtent;
      keyLight.shadow.camera.bottom = -shadowExtent;
      keyLight.shadow.camera.near = 0.5;
      keyLight.shadow.camera.far = radius * 12;
      keyLight.shadow.camera.updateProjectionMatrix();
      keyLight.position.set(
        sphere.center.x + radius * 1.1,
        sphere.center.y + radius * 2.4,
        sphere.center.z + radius * 1.35,
      );
      if (scene.fog instanceof THREE.Fog) {
        scene.fog.near = radius * 2.2;
        scene.fog.far = radius * 9;
      }
    };

    type CameraTween = {
      active: boolean;
      startMs: number;
      fromPos: THREE.Vector3;
      toPos: THREE.Vector3;
      fromTarget: THREE.Vector3;
      toTarget: THREE.Vector3;
      fromNear: number;
      toNear: number;
      fromFar: number;
      toFar: number;
    };
    const cameraTween: CameraTween = {
      active: false,
      startMs: 0,
      fromPos: new THREE.Vector3(),
      toPos: new THREE.Vector3(),
      fromTarget: new THREE.Vector3(),
      toTarget: new THREE.Vector3(),
      fromNear: camera.near,
      toNear: camera.near,
      fromFar: camera.far,
      toFar: camera.far,
    };

    const easeInOutCubic = (t: number) =>
      t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

    const smoothCameraTo = (
      position: THREE.Vector3,
      target: THREE.Vector3,
      near = camera.near,
      far = camera.far,
    ) => {
      cameraTween.active = true;
      cameraTween.startMs = performance.now();
      cameraTween.fromPos.copy(camera.position);
      cameraTween.toPos.copy(position);
      cameraTween.fromTarget.copy(controls.target);
      cameraTween.toTarget.copy(target);
      cameraTween.fromNear = camera.near;
      cameraTween.toNear = near;
      cameraTween.fromFar = camera.far;
      cameraTween.toFar = far;
    };

    const applyFitResult = (request: FitRequest) => {
      const result = resolveFitBounds({
        request,
        meshes: fitMeshIndex,
        fallbackGroup: hierarchy.allContent,
      });
      if (!result) return;
      configurePresentationDepth(result.sphere, result.bounds);
      const direction =
        request.target === "arch" && request.arch === "lower"
          ? PRESET_DIRECTIONS.lower
          : request.target === "arch" && request.arch === "upper"
            ? PRESET_DIRECTIONS.upper
            : new THREE.Vector3(0, 0.75, 2.35);
      const position = cameraPositionForSphere(result.sphere, direction, request.target === "selected" ? 2.1 : 2.5);
      const { near, far } = nearFarForSphere(result.sphere);
      smoothCameraTo(position, result.sphere.center.clone(), near, far);
    };

    const fit = (request: FitRequest = { target: "case" }) => applyFitResult(request);
    const setView = (view: CameraPresetId) => {
      const bounds = new THREE.Box3().setFromObject(hierarchy.allContent);
      if (bounds.isEmpty()) return;
      const sphere = bounds.getBoundingSphere(new THREE.Sphere());
      const position = cameraPositionForSphere(sphere, PRESET_DIRECTIONS[view], 2.5);
      const { near, far } = nearFarForSphere(sphere);
      smoothCameraTo(position, sphere.center.clone(), near, far);
    };
    const reset = () => {
      smoothCameraTo(new THREE.Vector3(0, 10, 17), new THREE.Vector3(0, 0, 0), 0.1, 1000);
    };

    // Instant first fit so the case is framed before transitions run.
    {
      const bounds = new THREE.Box3().setFromObject(hierarchy.allContent);
      if (!bounds.isEmpty()) {
        const sphere = bounds.getBoundingSphere(new THREE.Sphere());
        configurePresentationDepth(sphere, bounds);
        camera.position.set(
          sphere.center.x,
          sphere.center.y + sphere.radius * 0.75,
          sphere.center.z + sphere.radius * 2.35,
        );
        controls.target.copy(sphere.center);
        const depth = nearFarForSphere(sphere);
        camera.near = depth.near;
        camera.far = depth.far;
        camera.updateProjectionMatrix();
        controls.update();
      }
    }

    fitRef.current = fit;
    resetRef.current = reset;
    viewRef.current = setView;

    const applyVisibility = () => {
      const filters = visibilityRef.current;
      setArchGroupVisibility(hierarchy, "upper", filters.effectiveShowUpper);
      setArchGroupVisibility(hierarchy, "lower", filters.effectiveShowLower);
      records.forEach((record) => {
        const visible = toothPassesFilter(record.tooth);
        record.mesh.visible = visible;
        record.material.wireframe = filters.wireframe;
        record.material.transparent = filters.wireframe || record.material.transparent;
        record.label.style.visibility = visible ? "visible" : "hidden";
      });
      hierarchy.treatmentLayer.traverse((object) => {
        if (object.userData.role === "target-ghost" || object.userData.role === "movement-vector") {
          const arch = object.userData.arch as "upper" | "lower" | undefined;
          const instanceId = object.userData.instanceId as number | undefined;
          const toothKey = object.userData.toothKey as string | undefined;
          let visible = true;
          if (arch === "upper" && !filters.effectiveShowUpper) visible = false;
          if (arch === "lower" && !filters.effectiveShowLower) visible = false;
          if (instanceId != null && filters.hiddenToothIds.has(instanceId)) visible = false;
          if (filters.isolatedToothKey && toothKey && toothKey !== filters.isolatedToothKey) {
            visible = false;
          }
          object.visible = visible;
        }
      });
      originalObjects.traverse((object) => {
        if (object.userData.role !== "original-scan") return;
        const arch = object.userData.arch as "upper" | "lower";
        object.visible =
          arch === "upper" ? filters.effectiveShowUpper : filters.effectiveShowLower;
      });
      // Isolate mode: hide gingiva so a single tooth reads clearly.
      hierarchy.upperGingiva.visible =
        filters.effectiveShowUpper && filters.isolatedToothKey == null;
      hierarchy.lowerGingiva.visible =
        filters.effectiveShowLower && filters.isolatedToothKey == null;
    };
    applyVisibilityRef.current = applyVisibility;

    const applyVisuals = () => {
      const liveSelected = selectedToothRef.current;
      const multi = new Set(multiSelectedRef.current);
      const hovered = hoveredKeyRef.current;
      const filters = visibilityRef.current;
      records.forEach((record) => {
        const selected = liveSelected != null && toothMatchesKey(record.tooth, liveSelected);
        const multiSelected = !selected && multi.has(record.toothKey);
        const hoveredTooth = !selected && hovered === record.toothKey;
        const style = toothVisualStyle({
          arch: record.tooth.arch,
          selected,
          hovered: hoveredTooth,
          multiSelected,
          validationStatus: record.tooth.validationStatus,
        });
        record.colorTarget.set(style.color);
        record.emissiveTarget.set(style.emissive);
        record.emissiveIntensityTarget = style.emissiveIntensity;
        record.opacityTarget = style.opacity;
        record.material.roughness = style.roughness;
        record.material.envMapIntensity = style.envMapIntensity;
        record.material.transparent = style.transparent || filters.wireframe;
        record.material.wireframe = filters.wireframe;
        record.label.classList.toggle("is-selected", selected);
        record.label.classList.toggle("is-hovered", hoveredTooth);
      });
      refreshGhostHighlight(liveSelected);
    };
    applyVisualsRef.current = applyVisuals;

    const pointer = new THREE.Vector2();
    const raycaster = new THREE.Raycaster();
    let pointerDown: { x: number; y: number } | null = null;

    const handlePointerDown = (event: PointerEvent) => {
      pointerDown = { x: event.clientX, y: event.clientY };
    };
    const handlePointerMove = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      const hit = pickToothFromPointer(raycaster, camera, pointer, raycastMeshes, {
        preferBvh: true,
      });
      const nextHover = hit?.toothKey ?? null;
      if (nextHover !== hoveredKeyRef.current) {
        hoveredKeyRef.current = nextHover;
        applyVisuals();
      }
    };
    const handlePointerUp = (event: PointerEvent) => {
      if (!pointerDown) return;
      const dx = event.clientX - pointerDown.x;
      const dy = event.clientY - pointerDown.y;
      pointerDown = null;
      // Ignore drag-orbits as clicks.
      if (dx * dx + dy * dy > 25) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      const hit = pickToothFromPointer(raycaster, camera, pointer, raycastMeshes, {
        preferBvh: true,
      });
      if (hit?.toothKey) selectRef.current(hit.toothKey);
      else clearSelectRef.current?.();
    };
    renderer.domElement.addEventListener("pointerdown", handlePointerDown);
    renderer.domElement.addEventListener("pointermove", handlePointerMove);
    renderer.domElement.addEventListener("pointerup", handlePointerUp);

    let animationFrame = 0;
    const animate = () => {
      if (cameraTween.active) {
        const t = Math.min(1, (performance.now() - cameraTween.startMs) / CAMERA_TRANSITION_MS);
        const e = easeInOutCubic(t);
        camera.position.lerpVectors(cameraTween.fromPos, cameraTween.toPos, e);
        controls.target.lerpVectors(cameraTween.fromTarget, cameraTween.toTarget, e);
        camera.near = THREE.MathUtils.lerp(cameraTween.fromNear, cameraTween.toNear, e);
        camera.far = THREE.MathUtils.lerp(cameraTween.fromFar, cameraTween.toFar, e);
        camera.updateProjectionMatrix();
        if (t >= 1) cameraTween.active = false;
      }
      controls.update();
      records.forEach((record) => {
        record.material.color.lerp(record.colorTarget, SELECTION_LERP);
        record.material.emissive.lerp(record.emissiveTarget, SELECTION_LERP);
        record.material.emissiveIntensity = THREE.MathUtils.lerp(
          record.material.emissiveIntensity,
          record.emissiveIntensityTarget,
          SELECTION_LERP,
        );
        record.material.opacity = THREE.MathUtils.lerp(
          record.material.opacity,
          record.opacityTarget,
          SELECTION_LERP,
        );
        const point = new THREE.Vector3(...toothDisplayCentroid(record.tooth)).project(camera);
        record.label.style.transform = `translate(-50%, -50%) translate(${(point.x * 0.5 + 0.5) * container.clientWidth}px, ${(-point.y * 0.5 + 0.5) * container.clientHeight}px)`;
        const labelVisible =
          record.mesh.visible && point.z < 1 && layers["tooth-labels"].visible;
        record.label.style.display = labelVisible ? "block" : "none";
      });
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(animate);
    };
    animate();

    ghostHighlightRef.current = refreshGhostHighlight;
    applyVisibility();
    applyVisuals();
    const liveSelected = selectedToothRef.current;
    const liveSelectedRecord = records.find(({ tooth }) =>
      liveSelected != null ? toothMatchesKey(tooth, liveSelected) : false,
    );
    if (liveSelectedRecord) transformControls.attach(liveSelectedRecord.mesh);
    else transformControls.detach();

    const handleResize = () => {
      const width = Math.max(1, container.clientWidth);
      const height = Math.max(1, container.clientHeight);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    window.addEventListener("resize", handleResize);
    const resizeObserver =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(handleResize) : null;
    resizeObserver?.observe(container);

    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", handleResize);
      resizeObserver?.disconnect();
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.domElement.removeEventListener("pointermove", handlePointerMove);
      renderer.domElement.removeEventListener("pointerup", handlePointerUp);
      controls.dispose();
      transformControls.removeEventListener("objectChange", handleGizmoChange);
      transformControls.removeEventListener("dragging-changed", handleDragging);
      transformControls.dispose();
      gizmoRef.current = null;
      ghostHighlightRef.current = null;
      applyVisualsRef.current = null;
      applyVisibilityRef.current = null;
      environment.dispose();
      disposeObjectTree(hierarchy.allContent);
      disposeObjectTree(presentationObjects);
      renderer.dispose();
      labels.forEach((label) => label.remove());
      recordsRef.current = [];
    };
    // Visibility/wireframe/gizmoMode are applied by dedicated effects so arch filters
    // do not rebuild BufferGeometry + BVH (WP-12).
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sceneGraph/target/original only
  }, [
    sceneGraph,
    targetStage,
    showOriginal,
    originalOpacity,
  ]);

  useEffect(() => {
    applyVisibilityRef.current?.();
    applyVisualsRef.current?.();
  }, [
    effectiveShowLower,
    effectiveShowUpper,
    wireframe,
    hiddenToothIds,
    isolatedArch,
    isolatedToothKey,
  ]);

  useEffect(() => {
    const selectedRecord = recordsRef.current.find(({ tooth }) =>
      selectedTooth != null ? toothMatchesKey(tooth, selectedTooth) : false,
    );
    const allowTransform = transformEnabled && selectedRecord != null;
    if (allowTransform) gizmoRef.current?.attach(selectedRecord.mesh);
    else gizmoRef.current?.detach();
    gizmoRef.current?.setMode(gizmoMode);
    if (gizmoRef.current) gizmoRef.current.enabled = allowTransform;
    applyVisualsRef.current?.();
  }, [gizmoMode, selectedTooth, multiSelectedTeeth, transformEnabled]);

  return (
    <div className="viewport-shell" data-testid="viewport-shell">
      <div ref={containerRef} className="stage-viewport" data-testid="stage-viewer" />
      {contextualToolbar}
      <div className="viewport-toolbar" aria-label="3D camera controls">
        {CAMERA_PRESETS.map((preset) => (
          <button
            className="viewer-tool"
            key={preset.id}
            onClick={() => viewRef.current?.(preset.id)}
            title={`${preset.label} view`}
            data-testid={`camera-view-${preset.id}`}
          >
            {preset.label}
          </button>
        ))}
        <button
          className="viewer-tool"
          onClick={() => {
            fitRef.current?.({ target: "case" });
            onFit();
          }}
          title="Fit complete case"
          data-testid="camera-fit-case"
        >
          Fit case
        </button>
        <button
          className="viewer-tool"
          onClick={() =>
            fitRef.current?.({
              target: "selected",
              selectedKey: selectedTooth,
            })
          }
          title="Fit selected tooth"
          disabled={!selectedTooth}
          data-testid="camera-fit-selected"
        >
          Fit tooth
        </button>
        <button
          className="viewer-tool"
          onClick={() =>
            fitRef.current?.({
              target: "arch",
              arch: isolatedArch ?? (showUpper && !showLower ? "upper" : "lower"),
            })
          }
          title="Fit selected arch"
          data-testid="camera-fit-arch"
        >
          Fit arch
        </button>
        <button
          className="viewer-tool"
          onClick={() => {
            resetRef.current?.();
            onReset();
          }}
          title="Reset camera"
        >
          Reset
        </button>
        <span className="viewport-hint">Orbit · Pan · Zoom · Click empty to deselect</span>
      </div>
    </div>
  );
}
