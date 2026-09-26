import * as THREE from "three";

export type PresentationArch = "upper" | "lower";

export interface DentalMaterialProfiles {
  enamelCurrent: THREE.MeshStandardMaterialParameters;
  enamelUpper: THREE.MeshStandardMaterialParameters;
  enamelLower: THREE.MeshStandardMaterialParameters;
  enamelSelected: THREE.MeshStandardMaterialParameters;
  enamelTarget: THREE.MeshStandardMaterialParameters;
  enamelGhost: THREE.MeshStandardMaterialParameters;
  gingivaReal: THREE.MeshStandardMaterialParameters;
  gingivaVisualization: THREE.MeshStandardMaterialParameters;
  originalScanUpper: THREE.MeshStandardMaterialParameters;
  originalScanLower: THREE.MeshStandardMaterialParameters;
  collisionHighlight: THREE.MeshBasicMaterialParameters;
  contactHighlight: THREE.MeshBasicMaterialParameters;
  iprHighlight: THREE.MeshBasicMaterialParameters;
  movementVector: THREE.LineBasicMaterialParameters;
}

/**
 * Viewport presentation profiles only.
 * These values must never feed treatment math, validation, or export.
 */
export const dentalMaterialProfiles: DentalMaterialProfiles = {
  /** Warm ivory — current tooth surface. Visualization only, not enamel physics. */
  enamelCurrent: {
    color: 0xf3eadf,
    roughness: 0.42,
    metalness: 0.02,
    envMapIntensity: 0.48,
  },
  /** Slightly warmer ivory so the upper arch separates from the lower. */
  enamelUpper: {
    color: 0xf6efe6,
    roughness: 0.4,
    metalness: 0.02,
    envMapIntensity: 0.5,
  },
  /** Cooler ivory so the lower arch separates from the upper. */
  enamelLower: {
    color: 0xe6dccb,
    roughness: 0.46,
    metalness: 0.02,
    envMapIntensity: 0.42,
  },
  enamelSelected: {
    color: 0xe7c48a,
    roughness: 0.34,
    metalness: 0.02,
    emissive: 0x6a4520,
    emissiveIntensity: 0.18,
    envMapIntensity: 0.5,
  },
  /** Cool overlay for stored target geometry. Not a clinical approval color. */
  enamelTarget: {
    color: 0xd5e2ea,
    roughness: 0.5,
    metalness: 0.02,
    envMapIntensity: 0.32,
    transparent: true,
    opacity: 0.68,
    depthWrite: false,
  },
  enamelGhost: {
    color: 0xb7c6d0,
    roughness: 0.55,
    metalness: 0.01,
    envMapIntensity: 0.28,
    transparent: true,
    opacity: 0.55,
    depthWrite: false,
  },
  gingivaReal: {
    color: 0xb89290,
    roughness: 0.74,
    metalness: 0,
    envMapIntensity: 0.26,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  },
  gingivaVisualization: {
    color: 0xb08c88,
    roughness: 0.76,
    metalness: 0,
    envMapIntensity: 0.22,
    transparent: true,
    opacity: 0.82,
    depthWrite: true,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  },
  originalScanUpper: {
    color: 0xa8c4b8,
    roughness: 0.7,
    metalness: 0,
    transparent: true,
    opacity: 0.28,
    depthWrite: false,
    side: THREE.DoubleSide,
  },
  originalScanLower: {
    color: 0x8fa6b6,
    roughness: 0.72,
    metalness: 0,
    transparent: true,
    opacity: 0.28,
    depthWrite: false,
    side: THREE.DoubleSide,
  },
  collisionHighlight: { color: 0xe05d55, transparent: true, opacity: 0.9 },
  contactHighlight: { color: 0xd7a94f, transparent: true, opacity: 0.9 },
  iprHighlight: { color: 0xd18b52, transparent: true, opacity: 0.85 },
  movementVector: { color: 0xd4ae5c, transparent: true, opacity: 0.9 },
};

/** Presentation-only: pick arch enamel tint without touching mesh data. */
export function enamelProfileForArch(arch: PresentationArch): THREE.MeshStandardMaterialParameters {
  return arch === "upper" ? dentalMaterialProfiles.enamelUpper : dentalMaterialProfiles.enamelLower;
}

/** Presentation-only: resolve a Three color from a profile color field. */
export function profileColor(value: THREE.ColorRepresentation | undefined, fallback: number): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") return new THREE.Color(value).getHex();
  if (value instanceof THREE.Color) return value.getHex();
  return fallback;
}
