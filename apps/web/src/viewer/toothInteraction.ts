/**
 * WP-04 Tooth Interaction Engine (frontend).
 *
 * Formalizes interaction state over existing MovementSummary / P4 apply path.
 * Does not invent clinical axes, FDI, or movement limits.
 */

import type { MovementSummary, ReviewToothMesh } from "../review/types";
import { cloneMovement, hasMovementChanges } from "../review/editing";
import { reviewToothKey } from "../viewer/toothKey";

export type InteractionPhase =
  | "idle"
  | "hovered"
  | "selected"
  | "actively_transforming"
  | "locked"
  | "excluded"
  | "review_required"
  | "unavailable";

export type ConstraintAvailability =
  | "not_configured"
  | "configured"
  | "violating"
  | "unavailable";

export type CoordinateSpace =
  | "world"
  | "engineering_local"
  | "clinical_local"
  | "unavailable";

export type EditProvenanceReason =
  | "doctor_edit"
  | "doctor_reset"
  | "gizmo_edit"
  | "numeric_edit"
  | "reset"
  | "system_restore";

export interface ToothTransformSnapshot {
  translationX: number;
  translationY: number;
  translationZ: number;
  rotation: number;
  tip: number;
  torque: number;
  angulation: number;
  intrusion: number;
  extrusion: number;
}

export interface ToothInteractionState {
  caseId: string | null;
  toothKey: string;
  toothRef: string | null;
  arch: "upper" | "lower" | null;
  fdiNumber: number | null;
  semanticLabel: number | null;
  baseTransform: ToothTransformSnapshot;
  currentTransform: ToothTransformSnapshot;
  draftMovement: MovementSummary;
  coordinateSpace: CoordinateSpace;
  locked: boolean;
  excluded: boolean;
  phase: InteractionPhase;
  constraintAvailability: ConstraintAvailability;
  transforming: boolean;
  clinicallyApproved: false;
  notes: string[];
}

export interface InteractionTransaction {
  transactionId: string;
  toothKey: string;
  before: MovementSummary;
  after: MovementSummary;
  reason: EditProvenanceReason;
  timestamp: string;
  grouped: boolean;
}

export function movementToSnapshot(movement: MovementSummary): ToothTransformSnapshot {
  return {
    translationX: movement.translationX,
    translationY: movement.translationY,
    translationZ: movement.translationZ,
    rotation: movement.rotation,
    tip: movement.tip,
    torque: movement.torque,
    angulation: movement.angulation ?? 0,
    intrusion: movement.intrusion,
    extrusion: movement.extrusion,
  };
}

export function resolvePhase(input: {
  locked: boolean;
  excluded: boolean;
  selected: boolean;
  transforming: boolean;
  hovered?: boolean;
  available?: boolean;
}): InteractionPhase {
  if (input.available === false) return "unavailable";
  if (input.locked) return "locked";
  if (input.excluded) return "excluded";
  if (input.transforming) return "actively_transforming";
  if (input.selected) return "selected";
  if (input.hovered) return "hovered";
  return "idle";
}

/** Geometric manipulability — not clinical permission. */
export function canTransformTooth(movement: MovementSummary | null | undefined): boolean {
  if (!movement) return false;
  return !movement.locked && !movement.excluded;
}

export function resolveCoordinateSpace(tooth: ReviewToothMesh | null): CoordinateSpace {
  if (!tooth) return "unavailable";
  const frame = tooth.coordinateSystem ?? tooth.movementReferenceFrame;
  if (!frame) return "world";
  const semantics = frame.semantics ?? [];
  const engineering = semantics.some(
    (item) =>
      String(item).toLowerCase().includes("engineering") ||
      String(item).toLowerCase().includes("reconstructed"),
  );
  if (engineering) return "engineering_local";
  // Upstream frames without clinical verification are not clinical_local.
  return "engineering_local";
}

export function resolveConstraintAvailability(
  limitStatus: ReviewToothMesh["limitStatus"] | null | undefined,
): ConstraintAvailability {
  if (limitStatus == null || limitStatus === "not_configured") return "unavailable";
  if (limitStatus === "exceeded") return "violating";
  if (limitStatus === "within_configured_limit") return "configured";
  return "unavailable";
}

export function buildToothInteractionState(input: {
  caseId: string | null;
  tooth: ReviewToothMesh;
  draft: MovementSummary;
  base: MovementSummary;
  selected: boolean;
  transforming: boolean;
  hovered?: boolean;
}): ToothInteractionState {
  const locked = Boolean(input.draft.locked);
  const excluded = Boolean(input.draft.excluded);
  const coordinateSpace = resolveCoordinateSpace(input.tooth);
  const constraintAvailability = resolveConstraintAvailability(input.tooth.limitStatus);
  const notes: string[] = [];
  if (coordinateSpace !== "clinical_local") {
    notes.push(
      "Transforms are geometric; clinical dental-axis movement is not available without verified axes.",
    );
  }
  if (constraintAvailability === "unavailable" || constraintAvailability === "not_configured") {
    notes.push(
      "Movement constraints are not configured; a successful transform is not clinically validated.",
    );
  }
  notes.push("Interaction never implies doctor approval.");
  return {
    caseId: input.caseId,
    toothKey: reviewToothKey(input.tooth),
    toothRef: input.tooth.toothRef ?? null,
    arch: input.tooth.arch,
    fdiNumber: input.tooth.fdiNumber,
    semanticLabel: input.tooth.semanticLabel ?? null,
    baseTransform: movementToSnapshot(input.base),
    currentTransform: movementToSnapshot(input.draft),
    draftMovement: cloneMovement(input.draft),
    coordinateSpace,
    locked,
    excluded,
    phase: resolvePhase({
      locked,
      excluded,
      selected: input.selected,
      transforming: input.transforming,
      hovered: input.hovered,
    }),
    constraintAvailability,
    transforming: input.transforming,
    clinicallyApproved: false,
    notes,
  };
}

export function beginTransformTransaction(
  toothKey: string,
  before: MovementSummary,
  reason: EditProvenanceReason = "gizmo_edit",
): InteractionTransaction {
  return {
    transactionId: `tx-${toothKey}-${Date.now()}`,
    toothKey,
    before: cloneMovement(before),
    after: cloneMovement(before),
    reason,
    timestamp: new Date().toISOString(),
    grouped: true,
  };
}

export function updateTransformTransaction(
  transaction: InteractionTransaction,
  after: MovementSummary,
): InteractionTransaction {
  return {
    ...transaction,
    after: cloneMovement(after),
  };
}

export function transactionHasChanges(transaction: InteractionTransaction): boolean {
  return hasMovementChanges(transaction.before, transaction.after);
}

export function normalizeClientEditReason(
  reason: EditProvenanceReason | undefined,
): EditProvenanceReason {
  if (
    reason === "gizmo_edit" ||
    reason === "numeric_edit" ||
    reason === "doctor_reset" ||
    reason === "reset" ||
    reason === "system_restore" ||
    reason === "doctor_edit"
  ) {
    return reason === "reset" ? "doctor_reset" : reason;
  }
  return "doctor_edit";
}
