import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { SceneLayerRegistry } from "@alignerstudio/types";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { TransformControls } from "three/examples/jsm/controls/TransformControls.js";
import type { ReviewStage, ReviewToothMesh } from "../review/types";
import type { MovementSummary } from "../review/types";
import type { DentalSceneGraph } from "./sceneGraph";
import { dentalMaterialProfiles } from "./materialProfiles";

interface StageViewerProps {
  stage?: ReviewStage;
  sceneGraph: DentalSceneGraph;
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
}

interface ToothRecord {
  mesh: THREE.Mesh;
  material: THREE.MeshStandardMaterial;
  label: HTMLDivElement;
  tooth: ReviewToothMesh;
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

export function StageViewer({
  sceneGraph,
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
}: StageViewerProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
  const fitRef = useRef<(() => void) | null>(null);
  const resetRef = useRef<(() => void) | null>(null);
  const viewRef = useRef<((view: ViewDirection) => void) | null>(null);
  const recordsRef = useRef<ToothRecord[]>([]);
  const selectRef = useRef(onSelectTooth);
  const gizmoRef = useRef<TransformControls | null>(null);
  const gizmoCallbackRef = useRef(onGizmoMovement);
  selectRef.current = onSelectTooth;
  gizmoCallbackRef.current = onGizmoMovement;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x080d12);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.replaceChildren(renderer.domElement);

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
        rotation: object.rotation.y,
        tip: object.rotation.x,
        torque: object.rotation.z,
        intrusion: 0,
        extrusion: 0,
      });
    };
    transformControls.addEventListener("objectChange", handleGizmoChange);
    const handleDragging = (event: { value: unknown }) => {
      controls.enabled = event.value !== true;
    };
    transformControls.addEventListener("dragging-changed", handleDragging);
    scene.add(new THREE.HemisphereLight(0xe8f6ff, 0x111820, 1.9));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.6);
    keyLight.position.set(6, 14, 10);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x76c9df, 1.1);
    fillLight.position.set(-10, 5, -8);
    scene.add(fillLight);

    const allObjects = new THREE.Group();
    const originalObjects = new THREE.Group();
    const toothObjects = new THREE.Group();
    const vectorObjects = new THREE.Group();
    allObjects.add(originalObjects, toothObjects, vectorObjects);
    scene.add(allObjects);
    const raycastMeshes: THREE.Mesh[] = [];
    const labels: HTMLDivElement[] = [];
    const records: ToothRecord[] = [];
    recordsRef.current = records;
    const layers: SceneLayerRegistry = sceneGraph.layers;
    const stage = sceneGraph.segmentedStage;

    if (showOriginal && layers["original-scan"].visible) {
      const loader = new STLLoader();
      for (const arch of ["upper", "lower"] as const) {
        const buffer = sceneGraph.originalScans[arch];
        if (!buffer) continue;
        const geometry = loader.parse(buffer.slice(0));
        geometry.computeVertexNormals();
        const material = new THREE.MeshStandardMaterial({
          color: arch === "upper" ? 0xb7d3c8 : 0x8da8b8,
          roughness: 0.68,
          transparent: true,
          opacity: originalOpacity,
          depthWrite: false,
          side: THREE.DoubleSide,
        });
        originalObjects.add(new THREE.Mesh(geometry, material));
      }
    }

    for (const tooth of stage.teeth) {
      const archVisible = tooth.arch === "upper"
        ? layers["upper-teeth"].visible && showUpper
        : layers["lower-teeth"].visible && showLower;
      if (!archVisible || !layers.segmentation.visible || hiddenToothIds.has(tooth.instanceId)) continue;
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(tooth.vertices.flatMap((vertex) => [...vertex]), 3));
      geometry.setIndex(tooth.faces.flatMap((face) => [...face]));
      geometry.computeVertexNormals();
      const material = new THREE.MeshStandardMaterial({
        ...dentalMaterialProfiles.enamelCurrent,
        wireframe,
      });
      const mesh = new THREE.Mesh(geometry, material);
      const toothKey = tooth.toothRef ?? `instance:${tooth.instanceId}`;
      mesh.userData.toothRef = toothKey;
      mesh.userData.instanceId = tooth.instanceId;
      toothObjects.add(mesh);
      raycastMeshes.push(mesh);
      const label = document.createElement("div");
      label.className = "stage-tooth-label";
      label.textContent = tooth.fdiNumber ? `FDI ${tooth.fdiNumber}` : `${toothKey} · semantic`;
      label.setAttribute("data-testid", `tooth-label-${tooth.instanceId}`);
      container.appendChild(label);
      labels.push(label);
      records.push({ mesh, material, label, tooth });
      if (layers["movement-vectors"].visible) {
        const origin = new THREE.Vector3(...(tooth.centroid ?? averageVertex(tooth.vertices)));
        const movement = new THREE.Vector3(
          tooth.movement.translationX,
          tooth.movement.translationY,
          tooth.movement.translationZ,
        );
        if (movement.lengthSq() > 0) {
          const vectorGeometry = new THREE.BufferGeometry().setFromPoints([
            origin,
            origin.clone().add(movement),
          ]);
          const vector = new THREE.Line(
            vectorGeometry,
            new THREE.LineBasicMaterial({ color: 0xf2c96d, linewidth: 2 }),
          );
          vectorObjects.add(vector);
        }
      }
    }

    const fit = () => {
      const bounds = new THREE.Box3().setFromObject(allObjects);
      if (bounds.isEmpty()) return;
      const sphere = bounds.getBoundingSphere(new THREE.Sphere());
      camera.position.set(sphere.center.x, sphere.center.y + sphere.radius * 0.75, sphere.center.z + sphere.radius * 2.35);
      controls.target.copy(sphere.center);
      camera.near = Math.max(0.01, sphere.radius / 100);
      camera.far = Math.max(100, sphere.radius * 20);
      camera.updateProjectionMatrix();
      controls.update();
    };
    const setView = (view: ViewDirection) => {
      const bounds = new THREE.Box3().setFromObject(allObjects);
      if (bounds.isEmpty()) return;
      const sphere = bounds.getBoundingSphere(new THREE.Sphere());
      camera.position.copy(sphere.center).addScaledVector(VIEW_DIRECTIONS[view], sphere.radius * 2.5);
      controls.target.copy(sphere.center);
      controls.update();
    };
    const reset = () => {
      camera.position.set(0, 10, 17);
      controls.target.set(0, 0, 0);
      controls.update();
    };
    fitRef.current = fit;
    resetRef.current = reset;
    viewRef.current = setView;
    fit();

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
      controls.update();
      records.forEach(({ label, tooth }) => {
        const point = new THREE.Vector3(...(tooth.centroid ?? averageVertex(tooth.vertices))).project(camera);
        label.style.transform = `translate(-50%, -50%) translate(${(point.x * 0.5 + 0.5) * container.clientWidth}px, ${(-point.y * 0.5 + 0.5) * container.clientHeight}px)`;
        label.style.display = point.z < 1 && layers["tooth-labels"].visible ? "block" : "none";
      });
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(animate);
    };
    animate();
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
      renderer.dispose();
      geometryCleanup(allObjects);
      labels.forEach((label) => label.remove());
      recordsRef.current = [];
    };
  }, [sceneGraph, showLower, showOriginal, showUpper, originalOpacity, wireframe, hiddenToothIds]);

  useEffect(() => {
    const selectedRecord = recordsRef.current.find(
      ({ tooth }) => (tooth.toothRef ?? `instance:${tooth.instanceId}`) === selectedTooth,
    );
    if (selectedRecord) gizmoRef.current?.attach(selectedRecord.mesh);
    else gizmoRef.current?.detach();
    gizmoRef.current?.setMode(gizmoMode);
    recordsRef.current.forEach(({ material, label, tooth }) => {
      const toothKey = tooth.toothRef ?? `instance:${tooth.instanceId}`;
      const selected = selectedTooth === toothKey;
      material.color.set(selected ? dentalMaterialProfiles.enamelSelected.color ?? 0xf0c875 : dentalMaterialProfiles.enamelCurrent.color ?? 0xe6d8bd);
      material.emissive.set(selected ? 0x6f4e16 : 0x000000);
      material.emissiveIntensity = selected ? 0.65 : 0;
      label.classList.toggle("is-selected", selected);
    });
  }, [gizmoMode, selectedTooth]);

  return (
    <div className="viewport-shell">
      <div ref={containerRef} className="stage-viewport" data-testid="stage-viewer" />
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

function averageVertex(vertices: readonly [number, number, number][]): [number, number, number] {
  if (vertices.length === 0) return [0, 0, 0];
  const sum = vertices.reduce((total, vertex) => [total[0] + vertex[0], total[1] + vertex[1], total[2] + vertex[2]], [0, 0, 0]);
  return [sum[0] / vertices.length, sum[1] / vertices.length, sum[2] / vertices.length];
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
