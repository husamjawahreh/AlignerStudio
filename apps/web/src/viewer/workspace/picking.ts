/**
 * BVH-capable picking foundation.
 *
 * Uses Three.js Raycaster today. Optionally enables three-mesh-bvh accelerated
 * raycasting for large meshes. Selection always returns existing mesh userData
 * keys — never invents FDI.
 */

import * as THREE from "three";
import {
  acceleratedRaycast,
  computeBoundsTree,
  disposeBoundsTree,
} from "three-mesh-bvh";

export interface PickingHit {
  object: THREE.Object3D;
  point: THREE.Vector3;
  distance: number;
  /** Semantic key from mesh userData.toothKey / toothRef — may be null. */
  toothKey: string | null;
}

export interface PickerOptions {
  /** When true, use BVH-accelerated raycast on prepared meshes. */
  preferBvh?: boolean;
}

let bvhAccelerated = false;

type BoundsTreeGeometry = THREE.BufferGeometry & {
  computeBoundsTree?: typeof computeBoundsTree;
  disposeBoundsTree?: typeof disposeBoundsTree;
  boundsTree?: unknown;
};

/** Enable three-mesh-bvh acceleration for Mesh raycasting. */
export function enableBvhAcceleration(): boolean {
  THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
  THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
  THREE.Mesh.prototype.raycast = acceleratedRaycast;
  bvhAccelerated = true;
  return true;
}

/** Attempt enable — always succeeds when the package is installed (FV-01 ADOPT). */
export async function tryEnableBvhAcceleration(): Promise<boolean> {
  return enableBvhAcceleration();
}

export function isBvhAccelerationEnabled(): boolean {
  return bvhAccelerated;
}

export function pickToothFromPointer(
  raycaster: THREE.Raycaster,
  camera: THREE.Camera,
  pointer: THREE.Vector2,
  candidates: readonly THREE.Object3D[],
  options: PickerOptions = {},
): PickingHit | null {
  void options.preferBvh;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects([...candidates], false);
  const hit = hits.find((item) => {
    const data = item.object.userData as { presentationOnly?: boolean; toothKey?: string };
    return !data.presentationOnly;
  });
  if (!hit) return null;
  const data = hit.object.userData as { toothKey?: string; toothRef?: string };
  return {
    object: hit.object,
    point: hit.point.clone(),
    distance: hit.distance,
    toothKey: data.toothKey ?? data.toothRef ?? null,
  };
}

/** Prepare a mesh for optional BVH after geometry is built. */
export function prepareMeshForPicking(mesh: THREE.Mesh): void {
  if (!bvhAccelerated) return;
  const geometry = mesh.geometry as BoundsTreeGeometry;
  if (geometry && typeof geometry.computeBoundsTree === "function") {
    geometry.computeBoundsTree();
  }
}
