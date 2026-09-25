/**
 * Named scene hierarchy for the clinical CAD workspace (WP-03).
 * Presentation structure only — clinical truth lives in domain/view-model state.
 */

import * as THREE from "three";

export interface CaseSceneHierarchy {
  caseRoot: THREE.Group;
  upperArch: THREE.Group;
  upperTeeth: THREE.Group;
  upperGingiva: THREE.Group;
  upperOverlays: THREE.Group;
  lowerArch: THREE.Group;
  lowerTeeth: THREE.Group;
  lowerGingiva: THREE.Group;
  lowerOverlays: THREE.Group;
  occlusionLayer: THREE.Group;
  treatmentLayer: THREE.Group;
  validationLayer: THREE.Group;
  measurementLayer: THREE.Group;
  referenceLayer: THREE.Group;
  interactionLayer: THREE.Group;
  annotationLayer: THREE.Group;
  /** Flat convenience group of all case content for fit/bounds. */
  allContent: THREE.Group;
}

/** Build the CaseRoot hierarchy. Groups start empty; StageViewer populates them. */
export function createCaseSceneHierarchy(): CaseSceneHierarchy {
  const caseRoot = new THREE.Group();
  caseRoot.name = "CaseRoot";

  const upperArch = new THREE.Group();
  upperArch.name = "UpperArch";
  upperArch.userData.arch = "upper";
  const upperTeeth = new THREE.Group();
  upperTeeth.name = "UpperTeeth";
  const upperGingiva = new THREE.Group();
  upperGingiva.name = "UpperGingiva";
  const upperOverlays = new THREE.Group();
  upperOverlays.name = "UpperOverlays";
  upperArch.add(upperTeeth, upperGingiva, upperOverlays);

  const lowerArch = new THREE.Group();
  lowerArch.name = "LowerArch";
  lowerArch.userData.arch = "lower";
  const lowerTeeth = new THREE.Group();
  lowerTeeth.name = "LowerTeeth";
  const lowerGingiva = new THREE.Group();
  lowerGingiva.name = "LowerGingiva";
  const lowerOverlays = new THREE.Group();
  lowerOverlays.name = "LowerOverlays";
  lowerArch.add(lowerTeeth, lowerGingiva, lowerOverlays);

  const occlusionLayer = new THREE.Group();
  occlusionLayer.name = "OcclusionLayer";
  occlusionLayer.visible = false;
  occlusionLayer.userData.truthState = "not_available";

  const treatmentLayer = new THREE.Group();
  treatmentLayer.name = "TreatmentLayer";

  const validationLayer = new THREE.Group();
  validationLayer.name = "ValidationLayer";

  const measurementLayer = new THREE.Group();
  measurementLayer.name = "MeasurementLayer";

  const referenceLayer = new THREE.Group();
  referenceLayer.name = "ReferenceLayer";

  const interactionLayer = new THREE.Group();
  interactionLayer.name = "InteractionLayer";

  const annotationLayer = new THREE.Group();
  annotationLayer.name = "AnnotationLayer";

  const allContent = new THREE.Group();
  allContent.name = "AllContent";

  caseRoot.add(
    upperArch,
    lowerArch,
    occlusionLayer,
    treatmentLayer,
    validationLayer,
    measurementLayer,
    referenceLayer,
    interactionLayer,
    annotationLayer,
  );
  allContent.add(caseRoot);

  return {
    caseRoot,
    upperArch,
    upperTeeth,
    upperGingiva,
    upperOverlays,
    lowerArch,
    lowerTeeth,
    lowerGingiva,
    lowerOverlays,
    occlusionLayer,
    treatmentLayer,
    validationLayer,
    measurementLayer,
    referenceLayer,
    interactionLayer,
    annotationLayer,
    allContent,
  };
}

export function setArchGroupVisibility(
  hierarchy: CaseSceneHierarchy,
  arch: "upper" | "lower",
  visible: boolean,
): void {
  if (arch === "upper") hierarchy.upperArch.visible = visible;
  else hierarchy.lowerArch.visible = visible;
}
