import { useEffect, useRef } from "react";
import * as THREE from "three";

/**
 * Minimal 3D viewer shell: renders an empty grid scene the treatment-plan
 * review step can later populate with segmented tooth meshes/stages.
 */
export function ViewerShell(): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0f14);

    const camera = new THREE.PerspectiveCamera(
      50,
      container.clientWidth / container.clientHeight,
      0.1,
      1000,
    );
    camera.position.set(30, 30, 30);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const grid = new THREE.GridHelper(60, 30, 0x3d7bfa, 0x232c37);
    scene.add(grid);

    const ambient = new THREE.AmbientLight(0xffffff, 0.6);
    const directional = new THREE.DirectionalLight(0x4fd7e0, 0.8);
    directional.position.set(20, 30, 20);
    scene.add(ambient, directional);

    let frameId = 0;
    const animate = () => {
      grid.rotation.y += 0.0015;
      renderer.render(scene, camera);
      frameId = requestAnimationFrame(animate);
    };
    animate();

    const handleResize = () => {
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", handleResize);
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      data-testid="viewer-shell"
      style={{
        width: "100%",
        height: 360,
        borderRadius: 8,
        overflow: "hidden",
        border: "1px solid var(--as-border)",
      }}
    />
  );
}
