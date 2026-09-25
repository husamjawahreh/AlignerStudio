/**
 * Persistent semantic identity for tooth selection.
 * Prefer toothRef; never invent FDI when absent.
 */

import type { ToothSelectionState } from "@alignerstudio/types";
import type { ReviewToothMesh } from "../../review/types";
import { findToothByKey, reviewToothKey, toothMatchesKey } from "../toothKey";

export interface SemanticToothIdentity {
  /** Stable selection key — toothRef preferred. */
  key: string;
  toothRef: string | null;
  semanticLabel: number | null;
  fdiNumber: number | null;
  arch: "upper" | "lower";
  instanceId: number;
  /** True only when an FDI number was provided by analysis — never fabricated here. */
  hasClinicalFdi: boolean;
}

export function semanticIdentityFromTooth(tooth: ReviewToothMesh): SemanticToothIdentity {
  return {
    key: reviewToothKey(tooth),
    toothRef: tooth.toothRef ?? null,
    semanticLabel: tooth.semanticLabel ?? null,
    fdiNumber: tooth.fdiNumber ?? null,
    arch: tooth.arch,
    instanceId: tooth.instanceId,
    hasClinicalFdi: tooth.fdiNumber != null,
  };
}

export function selectionStateFromIdentity(identity: SemanticToothIdentity | null): ToothSelectionState {
  if (!identity) {
    return {
      selectedToothRef: null,
      semanticIdentifier: null,
      fdiNumber: null,
      arch: null,
      confidence: null,
    };
  }
  return {
    selectedToothRef: identity.key,
    semanticIdentifier: identity.semanticLabel,
    fdiNumber: identity.fdiNumber,
    arch: identity.arch,
    confidence: null,
  };
}

/**
 * Re-resolve selection after stage/mesh reload using persistent identity.
 * Preserves toothRef across stages; does not invent FDI.
 */
export function preserveSelectionAcrossTeeth(
  previousKey: string | null,
  teeth: readonly ReviewToothMesh[],
): SemanticToothIdentity | null {
  if (!previousKey) return null;
  const match = findToothByKey(teeth, previousKey);
  return match ? semanticIdentityFromTooth(match) : null;
}

export function identitiesEqual(a: SemanticToothIdentity | null, b: SemanticToothIdentity | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  if (a.toothRef && b.toothRef) return a.toothRef === b.toothRef;
  return toothMatchesKey(
    { instanceId: a.instanceId, toothRef: a.toothRef, fdiNumber: a.fdiNumber },
    b.key,
  );
}
