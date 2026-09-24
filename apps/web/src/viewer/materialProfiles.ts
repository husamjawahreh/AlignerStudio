import * as THREE from "three";

export interface DentalMaterialProfiles {
  enamelCurrent: THREE.MeshStandardMaterialParameters;
  enamelSelected: THREE.MeshStandardMaterialParameters;
  enamelTarget: THREE.MeshStandardMaterialParameters;
  enamelGhost: THREE.MeshStandardMaterialParameters;
  gingivaReal: THREE.MeshStandardMaterialParameters;
  gingivaVisualization: THREE.MeshStandardMaterialParameters;
  collisionHighlight: THREE.MeshBasicMaterialParameters;
  contactHighlight: THREE.MeshBasicMaterialParameters;
  iprHighlight: THREE.MeshBasicMaterialParameters;
  movementVector: THREE.LineBasicMaterialParameters;
}

export const dentalMaterialProfiles: DentalMaterialProfiles = {
  enamelCurrent: { color: 0xe6d8bd, roughness: 0.42, metalness: 0.02 },
  enamelSelected: { color: 0xf0c875, roughness: 0.32, metalness: 0.02, emissive: 0x5a3e14, emissiveIntensity: 0.45 },
  enamelTarget: { color: 0xf3ead6, roughness: 0.36, metalness: 0.01 },
  enamelGhost: { color: 0xd9e2df, roughness: 0.6, transparent: true, opacity: 0.24, depthWrite: false },
  gingivaReal: { color: 0xb87578, roughness: 0.7, metalness: 0 },
  gingivaVisualization: { color: 0xa9656e, roughness: 0.78, metalness: 0, transparent: true, opacity: 0.72 },
  collisionHighlight: { color: 0xe05d55, transparent: true, opacity: 0.9 },
  contactHighlight: { color: 0xd7a94f, transparent: true, opacity: 0.9 },
  iprHighlight: { color: 0xd18b52, transparent: true, opacity: 0.85 },
  movementVector: { color: 0xd2a653, transparent: true, opacity: 0.9 },
};
