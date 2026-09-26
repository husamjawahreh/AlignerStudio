/**
 * Deterministic dental-CAD studio lighting.
 * Lights live in scene space so orbit does not swing the key light.
 * This is visualization only. It does not describe enamel physics.
 */

import * as THREE from "three";

/** Neutral studio gray. Readable against ivory and cool target geometry. */
export const STUDIO_BACKGROUND = 0x243038;

export const RENDERING_PREPROCESS = {
  vertexNormals:
    "Normals are computed on a copied BufferGeometry. Source vertex arrays are not written.",
  gingivaOffset:
    "Synthetic and real gingiva materials use polygonOffset so the cervical band does not z-fight tooth surfaces. Offsets are not written back to geometry.",
} as const;

/** Visual-only updates must not rebuild geometry, BVH, or the camera. */
export const INCREMENTAL_UPDATE_POLICY = {
  selection: "material color targets only",
  hover: "material color targets only",
  archVisibility: "group visibility only",
  labels: "DOM display only",
  lighting: "installed once with the scene",
  materials: "profile parameters only",
} as const;

export const ORDINARY_SELECTION_MOVES_CAMERA = false;

/** The only case scene graph. Wave 4 does not add a second one. */
export const SCENE_GRAPH_FACTORY = "createCaseSceneHierarchy" as const;

export function installDentalStudioLighting(scene: THREE.Scene): void {
  scene.background = new THREE.Color(STUDIO_BACKGROUND);
  scene.fog = null;

  const hemisphere = new THREE.HemisphereLight(0xf7f4ee, 0x9aa3a8, 0.72);
  hemisphere.name = "StudioHemisphere";
  scene.add(hemisphere);

  const key = new THREE.DirectionalLight(0xfff8f0, 1.28);
  key.name = "StudioKey";
  key.position.set(6, 14, 10);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.bias = -0.00015;
  key.shadow.normalBias = 0.03;
  key.shadow.radius = 3;
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xd7e0e6, 0.52);
  fill.name = "StudioFill";
  fill.position.set(-11, 8, 6);
  scene.add(fill);

  const rim = new THREE.DirectionalLight(0xe6d8c6, 0.26);
  rim.name = "StudioRim";
  rim.position.set(1, 5, -14);
  scene.add(rim);

  const bounce = new THREE.DirectionalLight(0xc5ced4, 0.2);
  bounce.name = "StudioBounce";
  bounce.position.set(0, -8, 4);
  scene.add(bounce);
}
