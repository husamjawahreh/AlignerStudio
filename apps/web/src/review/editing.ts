import type { MovementSummary, ReviewBundle, ReviewEditRecord, ReviewStage } from "./types";
import { toothMatchesKey } from "../viewer/toothKey";

export type MovementField = keyof MovementSummary;

export const MOVEMENT_FIELDS: readonly MovementField[] = [
  "translationX",
  "translationY",
  "translationZ",
  "rotation",
  "tip",
  "torque",
  "intrusion",
  "extrusion",
];

export function cloneMovement(movement: MovementSummary): MovementSummary {
  return { ...movement };
}

export function hasMovementChanges(first: MovementSummary, second: MovementSummary): boolean {
  return MOVEMENT_FIELDS.some((field) => first[field] !== second[field]);
}

export function applyFixtureMovementEdit(
  bundle: ReviewBundle,
  toothNumber: number | string,
  movement: MovementSummary,
  timestamp: string,
  reason: "doctor_edit" | "doctor_reset" = "doctor_edit",
): ReviewBundle {
  const current = findTooth(bundle.stages.at(-1) ?? bundle.stages[0], toothNumber)?.movement;
  if (!current) throw new Error(`Tooth ${toothNumber} is not editable`);
  const editSeed = JSON.stringify({
    toothNumber,
    current,
    movement,
    timestamp,
    reason,
    version: bundle.proposalKind,
  });
  const editId = stableHash(editSeed);
  const edit: ReviewEditRecord = {
    editId,
    toothNumber,
    previousMovement: cloneMovement(current),
    newMovement: cloneMovement(movement),
    timestamp,
    versionId: stableHash(`${editSeed}:edit`),
    provenance: "generated",
    reason,
  };
  return rebuildFixtureBundle(bundle, toothNumber, movement, [edit, ...bundle.editHistory]);
}

export function resetFixtureTooth(
  bundle: ReviewBundle,
  toothNumber: number | string,
  timestamp: string,
): ReviewBundle {
  const firstEdit = [...bundle.editHistory]
    .reverse()
    .find((edit) => edit.toothNumber === toothNumber);
  if (!firstEdit) return bundle;
  return applyFixtureMovementEdit(
    bundle,
    toothNumber,
    firstEdit.previousMovement,
    timestamp,
    "doctor_reset",
  );
}

export function resetAllFixtureEdits(bundle: ReviewBundle, timestamp: string): ReviewBundle {
  let result = bundle;
  const teeth = new Set(bundle.editHistory.map((edit) => edit.toothNumber));
  for (const toothNumber of teeth) result = resetFixtureTooth(result, toothNumber, timestamp);
  return result;
}

export function cancelFixtureEdits(original: ReviewBundle): ReviewBundle {
  return original;
}

export function recalculateFixtureBundle(bundle: ReviewBundle): ReviewBundle {
  return {
    ...bundle,
    proposalKind: "recalculated",
    stages: bundle.stages.map((stage) => ({
      ...stage,
      validationStatus: "unavailable",
      warnings: ["Edited fixture validation payload is unavailable from the current API."],
      collisionCount: 0,
      proximityCount: 0,
      contactCount: 0,
    })),
  };
}

function rebuildFixtureBundle(
  bundle: ReviewBundle,
  toothNumber: number | string,
  movement: MovementSummary,
  editHistory: readonly ReviewEditRecord[],
): ReviewBundle {
  const stages = bundle.stages.map((stage) => {
    const progress = stage.index / Math.max(bundle.stages.length - 1, 1);
    return {
      ...stage,
      teeth: stage.teeth.map((tooth) => {
        if (!toothMatchesKey(tooth, String(toothNumber))) return tooth;
        const source = bundle.stages[0].teeth.find((item) => toothMatchesKey(item, String(toothNumber)));
        if (!source) return tooth;
        return {
          ...tooth,
          vertices: transformFixtureVertices(source.vertices, movement, progress),
          movement: scaleMovement(movement, progress),
        };
      }),
    } as ReviewStage;
  });
  return {
    ...bundle,
    stages,
    proposalKind: "doctor_edited",
    editHistory,
  };
}

function findTooth(stage: ReviewStage | undefined, toothNumber: number | string) {
  if (!stage) return undefined;
  return stage.teeth.find((tooth) => toothMatchesKey(tooth, String(toothNumber)));
}

function scaleMovement(movement: MovementSummary, progress: number): MovementSummary {
  return {
    translationX: movement.translationX * progress,
    translationY: movement.translationY * progress,
    translationZ: movement.translationZ * progress,
    rotation: movement.rotation * progress,
    tip: movement.tip * progress,
    torque: movement.torque * progress,
    intrusion: movement.intrusion * progress,
    extrusion: movement.extrusion * progress,
  };
}

function transformFixtureVertices(
  vertices: readonly [number, number, number][],
  movement: MovementSummary,
  progress: number,
): [number, number, number][] {
  const scaled = scaleMovement(movement, progress);
  const radians = (scaled.rotation * Math.PI) / 180;
  const center = vertices
    .reduce(
      (sum, vertex) => [sum[0] + vertex[0], sum[1] + vertex[1], sum[2] + vertex[2]],
      [0, 0, 0],
    )
    .map((value) => value / vertices.length);
  return vertices.map(([x, y, z]) => {
    const localX = x - center[0];
    const localY = y - center[1];
    return [
      center[0] + localX * Math.cos(radians) - localY * Math.sin(radians) + scaled.translationX,
      center[1] + localX * Math.sin(radians) + localY * Math.cos(radians) + scaled.translationY,
      z + scaled.translationZ + scaled.extrusion - scaled.intrusion,
    ];
  });
}

function stableHash(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}
