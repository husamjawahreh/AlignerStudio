import type { ReviewToothMesh } from "../review/types";
import { reviewToothKey, toothMatchesKey } from "./toothKey";

export type Vec3 = [number, number, number];

export function averageVertex(vertices: readonly Vec3[]): Vec3 {
  if (vertices.length === 0) return [0, 0, 0];
  const sum = vertices.reduce(
    (total, vertex) =>
      [total[0] + vertex[0], total[1] + vertex[1], total[2] + vertex[2]] as Vec3,
    [0, 0, 0] as Vec3,
  );
  return [sum[0] / vertices.length, sum[1] / vertices.length, sum[2] / vertices.length];
}

export function toothDisplayCentroid(tooth: ReviewToothMesh): Vec3 {
  return tooth.centroid ? ([...tooth.centroid] as Vec3) : averageVertex(tooth.vertices);
}

/**
 * Remaining movement guide: current stage pose → target stage pose.
 * Uses staged centroids (vertices already include translation) — never
 * currentCentroid + movement.translation (that double-counts).
 */
export function remainingMovementEndpoints(
  current: ReviewToothMesh,
  target: ReviewToothMesh | null | undefined,
): { start: Vec3; end: Vec3 } | null {
  if (!target) return null;
  const start = toothDisplayCentroid(current);
  const end = toothDisplayCentroid(target);
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  const dz = end[2] - start[2];
  if (dx * dx + dy * dy + dz * dz < 1e-8) return null;
  return { start, end };
}

export function indexTeethByKey(
  teeth: readonly ReviewToothMesh[],
): Map<string, ReviewToothMesh> {
  const map = new Map<string, ReviewToothMesh>();
  for (const tooth of teeth) map.set(reviewToothKey(tooth), tooth);
  return map;
}

export function findMatchingTooth(
  teeth: readonly ReviewToothMesh[],
  source: ReviewToothMesh,
): ReviewToothMesh | null {
  const key = reviewToothKey(source);
  return teeth.find((tooth) => toothMatchesKey(tooth, key)) ?? null;
}
