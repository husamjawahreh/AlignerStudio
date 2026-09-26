/**
 * Deterministic camera fit targets for case / arch / selected tooth (WP-03).
 */

import * as THREE from "three";
import type { FitRequest } from "./cameraNavigation";
import { describeFitRequest } from "./cameraNavigation";

export interface FitBoundsResult {
  bounds: THREE.Box3;
  sphere: THREE.Sphere;
  label: string;
}

export function computeObjectBounds(objects: readonly THREE.Object3D[]): THREE.Box3 {
  const bounds = new THREE.Box3();
  for (const object of objects) {
    if (!object.visible) continue;
    bounds.expandByObject(object);
  }
  return bounds;
}

/**
 * Resolve fit bounds from mesh records keyed by toothKey / arch.
 * Selection identity is semantic key — never array index.
 */
export function resolveFitBounds(input: {
  request: FitRequest;
  meshes: ReadonlyArray<{
    object: THREE.Object3D;
    toothKey: string;
    arch: "upper" | "lower";
  }>;
  fallbackGroup: THREE.Object3D;
}): FitBoundsResult | null {
  const { request, meshes, fallbackGroup } = input;
  let targets: THREE.Object3D[] = [];

  if (request.target === "selected") {
    const keys = new Set(
      request.selectedKeys && request.selectedKeys.length > 0
        ? request.selectedKeys
        : request.selectedKey
          ? [request.selectedKey]
          : [],
    );
    targets = meshes.filter((item) => keys.has(item.toothKey)).map((item) => item.object);
  } else if (request.target === "arch") {
    const arch = request.arch;
    if (!arch) return null;
    targets = meshes.filter((item) => item.arch === arch).map((item) => item.object);
  } else {
    const visible = meshes.filter((item) => item.object.visible).map((item) => item.object);
    const bounds = visible.length > 0 ? computeObjectBounds(visible) : new THREE.Box3().setFromObject(fallbackGroup);
    if (bounds.isEmpty()) return null;
    return {
      bounds,
      sphere: bounds.getBoundingSphere(new THREE.Sphere()),
      label: describeFitRequest(request),
    };
  }

  if (targets.length === 0) return null;
  const bounds = computeObjectBounds(targets);
  if (bounds.isEmpty()) return null;
  return {
    bounds,
    sphere: bounds.getBoundingSphere(new THREE.Sphere()),
    label: describeFitRequest(request),
  };
}

/**
 * Distance / radius so a bounding sphere fills `fill` of the vertical FOV.
 * Higher fill frames the subject larger. Values stay below 1 so the silhouette
 * keeps a margin and does not clip the viewport edge.
 */
export function framingDistanceFactor(fovDegrees: number, fill: number): number {
  const clamped = Math.min(0.92, Math.max(0.45, fill));
  const half = THREE.MathUtils.degToRad((fovDegrees * clamped) / 2);
  const tangent = Math.tan(half);
  if (tangent < 1e-4) return 3.2;
  return 1 / tangent;
}

/** One fill per fit target. Selection is slightly closer than the full case. */
export const PRESENTATION_FIT_FILL = {
  case: 0.74,
  arch: 0.78,
  selection: 0.86,
} as const;

/**
 * Keep a view direction off the world-up axis.
 * A camera placed exactly on +Y with the default up vector rolls and hides the occlusal plane.
 */
export function stableViewDirection(direction: THREE.Vector3): THREE.Vector3 {
  const dir = direction.clone();
  if (dir.lengthSq() < 1e-8) dir.set(0, 0.55, 1);
  dir.normalize();
  if (Math.abs(dir.y) > 0.96) {
    dir.z += dir.y >= 0 ? 0.28 : -0.28;
    dir.normalize();
  }
  return dir;
}

/** Camera position for a sphere look-at — shared framing math. */
export function cameraPositionForSphere(
  sphere: THREE.Sphere,
  direction: THREE.Vector3,
  distanceFactor = 2.5,
): THREE.Vector3 {
  const dir = stableViewDirection(direction);
  return sphere.center.clone().addScaledVector(dir, Math.max(sphere.radius, 1) * distanceFactor);
}

export function nearFarForSphere(sphere: THREE.Sphere): { near: number; far: number } {
  const radius = Math.max(sphere.radius, 1);
  return {
    near: Math.max(0.01, radius / 100),
    far: Math.max(100, radius * 20),
  };
}
