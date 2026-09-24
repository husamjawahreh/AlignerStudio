import type { ReviewToothMesh } from "../review/types";

export type ToothKeySource = Pick<ReviewToothMesh, "instanceId" | "toothRef" | "fdiNumber">;

/**
 * Canonical tooth identity for selection / overlays.
 * Prefer semantic toothRef, then FDI, then instance fallback.
 */
export function reviewToothKey(tooth: ToothKeySource): string {
  if (tooth.toothRef) return tooth.toothRef;
  if (tooth.fdiNumber != null) return String(tooth.fdiNumber);
  return `instance:${tooth.instanceId}`;
}

/** Match a tooth against a selection key, including legacy instance: keys. */
export function toothMatchesKey(tooth: ToothKeySource, key: string): boolean {
  if (reviewToothKey(tooth) === key) return true;
  if (tooth.toothRef != null && tooth.toothRef === key) return true;
  if (tooth.fdiNumber != null && String(tooth.fdiNumber) === key) return true;
  if (`instance:${tooth.instanceId}` === key) return true;
  return false;
}

export function findToothByKey<T extends ToothKeySource>(
  teeth: readonly T[] | null | undefined,
  key: string | null | undefined,
): T | null {
  if (!teeth || key == null) return null;
  return teeth.find((tooth) => toothMatchesKey(tooth, key)) ?? null;
}
