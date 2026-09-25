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

interface StageViewerProps {
  stage?: ReviewStage;
  sceneGraph: DentalSceneGraph;
  /** Final/target stage for ghost overlay and remaining-movement vectors. */
  targetStage?: ReviewStage | null;
  selectedTooth: string | null;
  showUpper: boolean;
  showLower: boolean;
  showOriginal: boolean;
  originalOpacity: number;
  wireframe: boolean;
  hiddenToothIds: ReadonlySet<number>;
  onSelectTooth: (toothRef: string) => void;
  onFit: () => void;
  onReset: () => void;
  gizmoMode?: "translate" | "rotate";
  onGizmoMovement?: (movement: MovementSummary) => void;
  /** Selection-scoped controls rendered above the camera toolbar. */
  contextualToolbar?: ReactNode;
}

interface ToothRecord {
  mesh: THREE.Mesh;
  material: THREE.MeshStandardMaterial;
  label: HTMLDivElement;
  tooth: ReviewToothMesh;
  colorTarget: THREE.Color;
  emissiveTarget: THREE.Color;
  emissiveIntensityTarget: number;
}

type ViewDirection = "occlusal" | "front" | "back" | "left" | "right" | "upper" | "lower";

const VIEW_DIRECTIONS: Record<ViewDirection, THREE.Vector3> = {
  occlusal: new THREE.Vector3(0, 1, 0.01),
  front: new THREE.Vector3(0, 0.08, 1),
  back: new THREE.Vector3(0, 0.08, -1),
  left: new THREE.Vector3(-1, 0.08, 0),
  right: new THREE.Vector3(1, 0.08, 0),
  upper: new THREE.Vector3(0, 1, 0),
  lower: new THREE.Vector3(0, -1, 0),
};

const SCENE_BG = 0x06090d;
const CAMERA_TRANSITION_MS = 480;
const SELECTION_LERP = 0.18;

export function StageViewer({
  sceneGraph,
  targetStage = null,
  selectedTooth,
  showUpper,
  showLower,
  showOriginal,
  originalOpacity,
  wireframe,
  hiddenToothIds,
  onSelectTooth,
  onFit,
  onReset,
  gizmoMode = "translate",
  onGizmoMovement,
  contextualToolbar,
}: StageViewerProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
  const fitRef = useRef<(() => void) | null>(null);
  const resetRef = useRef<(() => void) | null>(null);
  const viewRef = useRef<((view: ViewDirection) => void) | null>(null);
  const recordsRef = useRef<ToothRecord[]>([]);
  const selectRef = useRef(onSelectTooth);
  const gizmoRef = useRef<TransformControls | null>(null);
  const gizmoCallbackRef = useRef(onGizmoMovement);
  const ghostHighlightRef = useRef<((key: string | null) => void) | null>(null);
  const selectedToothRef = useRef(selectedTooth);
  selectRef.current = onSelectTooth;
  gizmoCallbackRef.current = onGizmoMovement;
  selectedToothRef.current = selectedTooth;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(SCENE_BG);
    scene.fog = new THREE.Fog(SCENE_BG, 40, 120);

    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 1000);
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

    scene.add(new THREE.HemisphereLight(0xf7f1e6, 0x101820, 0.95));
    const keyLight = new THREE.DirectionalLight(0xfff4e8, 1.85);
    keyLight.position.set(8, 18, 10);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(2048, 2048);
    keyLight.shadow.bias = -0.00025;
    keyLight.shadow.normalBias = 0.02;
    keyLight.shadow.radius = 3.5;
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x9bb8c8, 0.7);
    fillLight.position.set(-12, 5, -6);
    scene.add(fillLight);
    const rimLight = new THREE.DirectionalLight(0xd4b78a, 0.55);
    rimLight.position.set(2, 6, -16);
    scene.add(rimLight);
    const bounceLight = new THREE.DirectionalLight(0xc8d0d6, 0.28);
    bounceLight.position.set(0, -10, 4);
    scene.add(bounceLight);

    const allObjects = new THREE.Group();
    const originalObjects = new THREE.Group();
    const toothObjects = new THREE.Group();
    const ghostObjects = new THREE.Group();
    const gingivaObjects = new THREE.Group();
    const vectorObjects = new THREE.Group();
    const presentationObjects = new THREE.Group();
    allObjects.add(originalObjects, gingivaObjects, ghostObjects, toothObjects, vectorObjects);
    scene.add(allObjects, presentationObjects);
    const raycastMeshes: THREE.Mesh[] = [];
    const labels: HTMLDivElement[] = [];
    const records: ToothRecord[] = [];
    recordsRef.current = records;
    const layers: SceneLayerRegistry = sceneGraph.layers;
    const stage = sceneGraph.segmentedStage;
    const targetTeeth = targetStage?.teeth ?? [];

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
        originalObjects.add(mesh);
      }
    }

    // Target / proposed-setup ghost overlay (presentation only, not raycast).
    if (layers["proposed-setup"].visible && targetTeeth.length > 0) {
      for (const tooth of targetTeeth) {
        const archVisible = tooth.arch === "upper"
          ? layers["upper-teeth"].visible && showUpper
          : layers["lower-teeth"].visible && showLower;
        if (!archVisible || hiddenToothIds.has(tooth.instanceId)) continue;
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
        mesh.userData.presentationOnly = true;
        mesh.userData.role = "target-ghost";
        mesh.userData.toothRef = reviewToothKey(tooth);
        ghostObjects.add(mesh);
      }
    }

    for (const tooth of stage.teeth) {
      const archVisible = tooth.arch === "upper"
        ? layers["upper-teeth"].visible && showUpper
        : layers["lower-teeth"].visible && showLower;
      if (!archVisible || !layers.segmentation.visible || hiddenToothIds.has(tooth.instanceId)) continue;
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
        wireframe,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      const key = reviewToothKey(tooth);
      mesh.userData.toothRef = key;
      mesh.userData.instanceId = tooth.instanceId;
      mesh.userData.arch = tooth.arch;
      toothObjects.add(mesh);
      raycastMeshes.push(mesh);
      const label = document.createElement("div");
      label.className = `stage-tooth-label is-${tooth.arch}`;
      label.textContent = tooth.fdiNumber ? `FDI ${tooth.fdiNumber}` : `${key} · semantic`;
      label.setAttribute("data-testid", `tooth-label-${tooth.instanceId}`);
      container.appendChild(label);
      labels.push(label);
      records.push({
        mesh,
        material,
        label,
        tooth,
        colorTarget: new THREE.Color(profileColor(baseProfile.color, 0xf2e8d4)),
        emissiveTarget: new THREE.Color(0x000000),
        emissiveIntensityTarget: 0,
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
          vectorObjects.add(vector);
        }
      }
    }

    if (layers["gingiva-base"].visible) {
      const gingivaMeshes = resolveGingivaPresentation(stage.teeth, sceneGraph.realGingiva, {
        includeUpper: showUpper && layers["upper-teeth"].visible,
        includeLower: showLower && layers["lower-teeth"].visible,
        hiddenToothIds,
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
        gingivaObjects.add(mesh);
      }
    }

    // Emphasize selected tooth's target ghost with enamelTarget profile.
    const refreshGhostHighlight = (selectedKey: string | null) => {
      ghostObjects.traverse((object) => {
        if (!(object instanceof THREE.Mesh)) return;
        const material = object.material;
        if (!(material instanceof THREE.MeshStandardMaterial)) return;
        const selected = selectedKey != null && object.userData.toothRef === selectedKey;
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

    const fit = () => {
      const bounds = new THREE.Box3().setFromObject(allObjects);
      if (bounds.isEmpty()) return;
      const sphere = bounds.getBoundingSphere(new THREE.Sphere());
      configurePresentationDepth(sphere, bounds);
      const position = new THREE.Vector3(
        sphere.center.x,
        sphere.center.y + sphere.radius * 0.75,
        sphere.center.z + sphere.radius * 2.35,
      );
      const near = Math.max(0.01, sphere.radius / 100);
      const far = Math.max(100, sphere.radius * 20);
      smoothCameraTo(position, sphere.center.clone(), near, far);
    };
    const setView = (view: ViewDirection) => {
      const bounds = new THREE.Box3().setFromObject(allObjects);
      if (bounds.isEmpty()) return;
      const sphere = bounds.getBoundingSphere(new THREE.Sphere());
      const position = sphere.center.clone().addScaledVector(VIEW_DIRECTIONS[view], sphere.radius * 2.5);
      smoothCameraTo(position, sphere.center.clone());
    };
    const reset = () => {
      smoothCameraTo(new THREE.Vector3(0, 10, 17), new THREE.Vector3(0, 0, 0));
    };

    // Instant first fit so the case is framed before transitions run.
    {
      const bounds = new THREE.Box3().setFromObject(allObjects);
      if (!bounds.isEmpty()) {
        const sphere = bounds.getBoundingSphere(new THREE.Sphere());
        configurePresentationDepth(sphere, bounds);
        camera.position.set(
          sphere.center.x,
          sphere.center.y + sphere.radius * 0.75,
          sphere.center.z + sphere.radius * 2.35,
        );
        controls.target.copy(sphere.center);
        camera.near = Math.max(0.01, sphere.radius / 100);
        camera.far = Math.max(100, sphere.radius * 20);
        camera.updateProjectionMatrix();
        controls.update();
      }
    }

    fitRef.current = fit;
    resetRef.current = reset;
    viewRef.current = setView;

    const pointer = new THREE.Vector2();
    const raycaster = new THREE.Raycaster();
    const handlePointer = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(raycastMeshes, false)[0];
      if (hit?.object.userData.toothRef) selectRef.current(hit.object.userData.toothRef as string);
    };
    renderer.domElement.addEventListener("pointerup", handlePointer);
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
        const point = new THREE.Vector3(...toothDisplayCentroid(record.tooth)).project(camera);
        record.label.style.transform = `translate(-50%, -50%) translate(${(point.x * 0.5 + 0.5) * container.clientWidth}px, ${(-point.y * 0.5 + 0.5) * container.clientHeight}px)`;
        record.label.style.display = point.z < 1 && layers["tooth-labels"].visible ? "block" : "none";
      });
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(animate);
    };
    animate();

    // Stash ghost highlight updater for the selection effect.
    ghostHighlightRef.current = refreshGhostHighlight;

    // Re-apply live selection after a scene rebuild (selection effect may not re-run).
    const liveSelected = selectedToothRef.current;
    refreshGhostHighlight(liveSelected);
    records.forEach((record) => {
      const selected = liveSelected != null && toothMatchesKey(record.tooth, liveSelected);
      const base = enamelProfileForArch(record.tooth.arch);
      const selectedProfile = dentalMaterialProfiles.enamelSelected;
      record.colorTarget.set(
        selected
          ? profileColor(selectedProfile.color, 0xf4d08a)
          : profileColor(base.color, record.tooth.arch === "upper" ? 0xf2e8d4 : 0xddd4c2),
      );
      record.emissiveTarget.set(selected ? 0x5a3c12 : 0x000000);
      record.emissiveIntensityTarget = selected ? 0.32 : 0;
      if (selected) {
        record.material.color.copy(record.colorTarget);
        record.material.emissive.copy(record.emissiveTarget);
        record.material.emissiveIntensity = record.emissiveIntensityTarget;
      }
      record.label.classList.toggle("is-selected", selected);
    });
    const liveSelectedRecord = records.find(({ tooth }) =>
      liveSelected != null ? toothMatchesKey(tooth, liveSelected) : false,
    );
    if (liveSelectedRecord) transformControls.attach(liveSelectedRecord.mesh);
    else transformControls.detach();

    const handleResize = () => {
      camera.aspect = container.clientWidth / Math.max(1, container.clientHeight);
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener("resize", handleResize);
    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", handleResize);
      renderer.domElement.removeEventListener("pointerup", handlePointer);
      controls.dispose();
      transformControls.removeEventListener("objectChange", handleGizmoChange);
      transformControls.removeEventListener("dragging-changed", handleDragging);
      transformControls.dispose();
      gizmoRef.current = null;
      ghostHighlightRef.current = null;
      environment.dispose();
      renderer.dispose();
      geometryCleanup(allObjects);
      geometryCleanup(presentationObjects);
      labels.forEach((label) => label.remove());
      recordsRef.current = [];
    };
  }, [sceneGraph, targetStage, showLower, showOriginal, showUpper, originalOpacity, wireframe, hiddenToothIds]);

  useEffect(() => {
    const selectedRecord = recordsRef.current.find(({ tooth }) =>
      selectedTooth != null ? toothMatchesKey(tooth, selectedTooth) : false,
    );
    if (selectedRecord) gizmoRef.current?.attach(selectedRecord.mesh);
    else gizmoRef.current?.detach();
    gizmoRef.current?.setMode(gizmoMode);
    ghostHighlightRef.current?.(selectedTooth);
    recordsRef.current.forEach((record) => {
      const selected = selectedTooth != null && toothMatchesKey(record.tooth, selectedTooth);
      const base = enamelProfileForArch(record.tooth.arch);
      const selectedProfile = dentalMaterialProfiles.enamelSelected;
      record.colorTarget.set(
        selected
          ? profileColor(selectedProfile.color, 0xf4d08a)
          : profileColor(base.color, record.tooth.arch === "upper" ? 0xf2e8d4 : 0xddd4c2),
      );
      record.emissiveTarget.set(selected ? 0x5a3c12 : 0x000000);
      record.emissiveIntensityTarget = selected ? 0.32 : 0;
      record.material.roughness = selected
        ? Number(selectedProfile.roughness ?? 0.22)
        : Number(base.roughness ?? 0.28);
      record.material.envMapIntensity = selected
        ? Number(selectedProfile.envMapIntensity ?? 1.2)
        : Number(base.envMapIntensity ?? 1);
      record.label.classList.toggle("is-selected", selected);
    });
  }, [gizmoMode, selectedTooth]);

  return (
    <div className="viewport-shell">
      <div ref={containerRef} className="stage-viewport" data-testid="stage-viewer" />
      {contextualToolbar}
      <div className="viewport-toolbar" aria-label="3D camera controls">
        {(["occlusal", "front", "back", "left", "right", "upper", "lower"] as ViewDirection[]).map((view) => (
          <button className="viewer-tool" key={view} onClick={() => viewRef.current?.(view)} title={`${view} view`}>{view}</button>
        ))}
        <button className="viewer-tool" onClick={() => { fitRef.current?.(); onFit(); }} title="Fit complete case">Fit</button>
        <button className="viewer-tool" onClick={() => { resetRef.current?.(); onReset(); }} title="Reset camera">Reset</button>
        <span className="viewport-hint">Orbit · Pan · Zoom</span>
      </div>
    </div>
  );
}

function geometryCleanup(group: THREE.Group): void {
  group.traverse((object) => {
    if (!(object instanceof THREE.Mesh) && !(object instanceof THREE.Line)) return;
    object.geometry.dispose();
    const material = object.material;
    if (Array.isArray(material)) material.forEach((item) => item.dispose());
    else material.dispose();
  });
}
