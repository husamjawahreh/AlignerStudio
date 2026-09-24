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
  /** Warm ivory — default / upper-arch readability. */
  enamelCurrent: {
    color: 0xf0e6d0,
    roughness: 0.28,
    metalness: 0.035,
    envMapIntensity: 1.05,
  },
  /** Warmer ivory for upper arch spatial separation. */
  enamelUpper: {
    color: 0xf2e8d4,
    roughness: 0.26,
    metalness: 0.04,
    envMapIntensity: 1.1,
  },
  /** Cooler ivory for lower arch spatial separation. */
  enamelLower: {
    color: 0xddd4c2,
    roughness: 0.32,
    metalness: 0.03,
    envMapIntensity: 0.95,
  },
  enamelSelected: {
    color: 0xf4d08a,
    roughness: 0.22,
    metalness: 0.05,
    emissive: 0x5a3c12,
    emissiveIntensity: 0.32,
    envMapIntensity: 1.2,
  },
  enamelTarget: {
    color: 0xf7f1e6,
    roughness: 0.3,
    metalness: 0.02,
    transparent: true,
    opacity: 0.7,
    depthWrite: false,
  },
  enamelGhost: {
    color: 0xd5ddd9,
    roughness: 0.55,
    transparent: true,
    opacity: 0.2,
    depthWrite: false,
  },
  gingivaReal: {
    color: 0xc4848a,
    roughness: 0.62,
    metalness: 0.02,
    envMapIntensity: 0.55,
  },
  gingivaVisualization: {
    color: 0xc07f86,
    roughness: 0.64,
    metalness: 0.02,
    envMapIntensity: 0.5,
    transparent: true,
    opacity: 0.92,
  },
  originalScanUpper: {
    color: 0xb9cfc4,
    roughness: 0.72,
    metalness: 0,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
  },
  originalScanLower: {
    color: 0x8fa6b6,
    roughness: 0.74,
    metalness: 0,
    transparent: true,
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
