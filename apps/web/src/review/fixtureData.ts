import type { ReviewBundle, ReviewStage, ReviewToothMesh } from "./types";

const FDI_TEETH = [11, 12, 13, 14, 41, 42, 43, 44] as const;
const FACES: readonly [number, number, number][] = [
  [0, 1, 2],
  [0, 2, 3],
  [4, 6, 5],
  [4, 7, 6],
  [0, 4, 5],
  [0, 5, 1],
  [1, 5, 6],
  [1, 6, 2],
  [2, 6, 7],
  [2, 7, 3],
  [3, 7, 4],
  [3, 4, 0],
];

function cuboidVertices(centerX: number, centerY: number, centerZ: number) {
  const halfWidth = 0.34;
  const halfDepth = 0.42;
  const halfHeight = 0.5;
  return [
    [centerX - halfWidth, centerY - halfDepth, centerZ - halfHeight],
    [centerX + halfWidth, centerY - halfDepth, centerZ - halfHeight],
    [centerX + halfWidth, centerY + halfDepth, centerZ - halfHeight],
    [centerX - halfWidth, centerY + halfDepth, centerZ - halfHeight],
    [centerX - halfWidth, centerY - halfDepth, centerZ + halfHeight],
    [centerX + halfWidth, centerY - halfDepth, centerZ + halfHeight],
    [centerX + halfWidth, centerY + halfDepth, centerZ + halfHeight],
    [centerX - halfWidth, centerY + halfDepth, centerZ + halfHeight],
  ] as [number, number, number][];
}

function toothMesh(fdiNumber: number, stageIndex: number): ReviewToothMesh {
  const isUpper = fdiNumber < 30;
  const position = isUpper ? fdiNumber - 11 : fdiNumber - 41;
  const centerX = (position - 1.5) * 1.05;
  const centerY = isUpper ? 0.8 + Math.abs(position - 1.5) * 0.08 : -0.8;
  const shift = stageIndex * (position === 1 ? 0.12 : position === 2 ? -0.08 : 0.04);
  return {
    instanceId: fdiNumber,
    fdiNumber,
    arch: isUpper ? "upper" : "lower",
    confidence: 0.98,
    vertices: cuboidVertices(centerX + shift, centerY, 0),
    faces: FACES,
    centroid: [centerX + shift, centerY, 0],
    movement: {
      translationX: shift,
      translationY: 0,
      translationZ: 0,
      rotation: stageIndex * (position === 1 ? 2 : 0),
      tip: 0,
      torque: 0,
      intrusion: 0,
      extrusion: 0,
    },
    validationStatus: stageIndex === 2 && position === 1 ? "warning" : "pass",
    validationMessage:
      stageIndex === 2 && position === 1
        ? "Fixture proximity warning for review demonstration."
        : "No fixture geometry findings.",
    provenance: "fixture",
    fixture: true,
  };
}

function stage(index: number): ReviewStage {
  const teeth = FDI_TEETH.map((fdiNumber) => toothMesh(fdiNumber, index));
  return {
    index,
    stageId: `fixture-stage-${index}`,
    teeth,
    validationStatus: index === 2 ? "warning" : "pass",
    collisionCount: 0,
    proximityCount: index === 2 ? 1 : 0,
    contactCount: 0,
    warnings: index === 2 ? ["Fixture proximity warning for review demonstration."] : [],
    provenance: "fixture",
    fixture: true,
  };
}

export const engineeringFixtureBundle: ReviewBundle = {
  stages: [stage(0), stage(1), stage(2)],
  provenance: "fixture",
  fixture: true,
  realDataAvailable: false,
  proposalKind: "original_generated",
  editHistory: [],
  iprSites: [
    {
      siteId: "fixture-ipr-11-12",
      toothA: 11,
      toothB: 12,
      currentDistance: 0.42,
      targetDistance: 0.31,
      proposedAmount: 0.11,
      status: "needs_review",
      warning: "Geometric space delta only; not a clinical IPR recommendation.",
      fixture: true,
    },
  ],
  attachmentSites: [
    {
      siteId: "fixture-attachment-13",
      toothNumber: 13,
      attachmentType: "undetermined",
      referencePoint: [0, 0, 0],
      reason: "Fixture angular movement candidate.",
      status: "needs_review",
      warning: "Shape and dimensions require doctor review; no validated geometry is generated.",
      fixture: true,
    },
  ],
  sourceKind: "development_treatment_fixture",
  experimental: true,
  unavailableReason:
    "Real staged mesh and validation payloads are not available from the current API.",
};
