import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { ReviewStage } from "../review/types";

interface StageViewerProps {
  stage: ReviewStage;
  selectedTooth: number | null;
  showUpper: boolean;
  showLower: boolean;
  showOriginal: boolean;
  wireframe: boolean;
  onSelectTooth: (fdiNumber: number) => void;
  onFit: () => void;
  onReset: () => void;
}

export function StageViewer({
  stage,
  selectedTooth,
  showUpper,
  showLower,
  showOriginal,
  wireframe,
  onSelectTooth,
  onFit,
  onReset,
}: StageViewerProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);
  const fitRef = useRef<(() => void) | null>(null);
  const resetRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x090d12);
    const camera = new THREE.PerspectiveCamera(
      42,
      container.clientWidth / container.clientHeight,
      0.1,
      1000,
    );
    camera.position.set(0, 10, 17);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.replaceChildren(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 0, 0);
    scene.add(new THREE.HemisphereLight(0xdbeeff, 0x101722, 1.8));
    const keyLight = new THREE.DirectionalLight(0x79dce6, 2.2);
    keyLight.position.set(5, 12, 8);
    scene.add(keyLight);
    scene.add(new THREE.GridHelper(24, 24, 0x29404e, 0x16242d));
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const meshes: THREE.Mesh[] = [];
    const allObjects = new THREE.Group();
    scene.add(allObjects);

    for (const tooth of stage.teeth) {
      if ((tooth.arch === "upper" && !showUpper) || (tooth.arch === "lower" && !showLower))
        continue;
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(
          tooth.vertices.flatMap((vertex) => [...vertex]),
          3,
        ),
      );
      geometry.setIndex(tooth.faces.flatMap((face) => [...face]));
      geometry.computeVertexNormals();
      const selected = selectedTooth === tooth.fdiNumber;
      const material = new THREE.MeshStandardMaterial({
        color: selected ? 0xf0c96a : tooth.arch === "upper" ? 0x8acbd0 : 0x557aa2,
        roughness: 0.42,
        metalness: 0.08,
        transparent: showOriginal,
        opacity: showOriginal ? 0.88 : 1,
        wireframe,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.userData.fdiNumber = tooth.fdiNumber;
      meshes.push(mesh);
      allObjects.add(mesh);
      if (showOriginal) {
        const originalMaterial = new THREE.MeshBasicMaterial({
          color: 0x71808d,
          wireframe: true,
          transparent: true,
          opacity: 0.28,
        });
        const original = new THREE.Mesh(geometry.clone(), originalMaterial);
        original.position.set(0, 0, -0.1);
        allObjects.add(original);
      }
    }

    const fit = () => {
      const bounds = new THREE.Box3().setFromObject(allObjects);
      if (bounds.isEmpty()) return;
      const sphere = bounds.getBoundingSphere(new THREE.Sphere());
      camera.position.set(
        sphere.center.x,
        sphere.center.y + sphere.radius * 0.7,
        sphere.center.z + sphere.radius * 2.2,
      );
      controls.target.copy(sphere.center);
      camera.near = Math.max(0.01, sphere.radius / 100);
      camera.far = Math.max(100, sphere.radius * 20);
      camera.updateProjectionMatrix();
      controls.update();
    };
    const reset = () => {
      camera.position.set(0, 10, 17);
      controls.target.set(0, 0, 0);
      controls.update();
    };
    fitRef.current = fit;
    resetRef.current = reset;
    fit();
    const handlePointer = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(meshes)[0];
      if (hit?.object.userData.fdiNumber) onSelectTooth(hit.object.userData.fdiNumber as number);
    };
    renderer.domElement.addEventListener("pointerup", handlePointer);
    let animationFrame = 0;
    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(animate);
    };
    animate();
    const handleResize = () => {
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener("resize", handleResize);
    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", handleResize);
      renderer.domElement.removeEventListener("pointerup", handlePointer);
      controls.dispose();
      renderer.dispose();
      geometryCleanup(allObjects);
    };
  }, [stage, selectedTooth, showUpper, showLower, showOriginal, wireframe, onSelectTooth]);

  function handleFit(): void {
    fitRef.current?.();
    onFit();
  }
  function handleReset(): void {
    resetRef.current?.();
    onReset();
  }

  return (
    <div className="viewport-shell">
      <div ref={containerRef} className="stage-viewport" data-testid="stage-viewer" />
      <div className="viewport-toolbar">
        <button className="viewer-tool" onClick={handleFit} title="Fit case">
          Fit
        </button>
        <button className="viewer-tool" onClick={handleReset} title="Reset view">
          Reset
        </button>
        <span className="viewport-hint">Orbit · Pan · Zoom</span>
      </div>
    </div>
  );
}

function geometryCleanup(group: THREE.Group): void {
  group.traverse((object) => {
    if (object instanceof THREE.Mesh) {
      object.geometry.dispose();
      const material = object.material;
      if (Array.isArray(material)) material.forEach((item) => item.dispose());
      else material.dispose();
    }
  });
}
