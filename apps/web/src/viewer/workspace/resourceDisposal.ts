/**
 * GPU resource disposal for workspace meshes — includes BVH trees (WP-03).
 */

import * as THREE from "three";
import { disposeBoundsTree } from "three-mesh-bvh";

type BoundsTreeGeometry = THREE.BufferGeometry & {
  disposeBoundsTree?: typeof disposeBoundsTree;
  boundsTree?: unknown;
};

export function disposeMeshResources(object: THREE.Object3D): void {
  if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
    const geometry = object.geometry as BoundsTreeGeometry | undefined;
    if (geometry) {
      if (geometry.boundsTree && typeof geometry.disposeBoundsTree === "function") {
        geometry.disposeBoundsTree();
      } else if (geometry.boundsTree) {
        // Ensure prototype method is available when BVH was enabled globally.
        try {
          disposeBoundsTree.call(geometry);
        } catch {
          // ignore — geometry may not have a tree
        }
      }
      geometry.dispose();
    }
    const material = object.material;
    if (Array.isArray(material)) material.forEach((item) => item.dispose());
    else if (material) material.dispose();
  }
}

export function disposeObjectTree(root: THREE.Object3D): void {
  root.traverse((object) => {
    disposeMeshResources(object);
  });
}

/** Snapshot of renderer/info counters for leak-oriented tests (best-effort). */
export function rendererResourceSnapshot(renderer: THREE.WebGLRenderer): {
  geometries: number;
  textures: number;
} {
  const info = renderer.info;
  return {
    geometries: info.memory.geometries,
    textures: info.memory.textures,
  };
}
