import type { ReviewBundle, ReviewStage, ReviewToothMesh, MovementSummary } from "./review/types";
import { formatToothIdentity } from "./analysisPresentation";
import { reviewToothKey, findToothByKey } from "./viewer/toothKey";

export interface SetupComparisonRow {
  toothKey: string;
  label: string;
  arch: string;
  initialMovement: number;
  targetMovement: number;
  delta: number;
}

function movementMagnitude(movement: MovementSummary | undefined): number {
  if (!movement) return 0;
  return Math.hypot(
    movement.translationX,
    movement.translationY,
    movement.translationZ,
  );
}

/** Presentation summary for Treatment Setup — no replanning math. */
export function buildTreatmentSetupSummary(bundle: ReviewBundle): {
  available: boolean;
  stageCount: number;
  proposalKind: string;
  planVersionLabel: string;
  setupAlternativesLabel: string;
  movedToothCount: number | null;
  totalMovement: number | null;
  source: string | null;
  doctorReviewRequired: boolean | null;
  warnings: readonly string[];
  initialStageLabel: string;
  targetStageLabel: string;
} {
  const stages = bundle.stages;
  const available = bundle.realDataAvailable && stages.length > 0;
  const initial = stages[0];
  const target = stages.at(-1);
  return {
    available,
    stageCount: stages.length,
    proposalKind: bundle.proposalKind.replaceAll("_", " "),
    planVersionLabel: available
      ? `${bundle.proposalKind.replaceAll("_", " ")} · ${stages.length} stages`
      : "Unavailable",
    setupAlternativesLabel: available
      ? "Single setup available"
      : "Unavailable",
    movedToothCount: bundle.planSummary?.movedToothCount ?? null,
    totalMovement: bundle.planSummary?.totalMovement ?? null,
    source: bundle.planSummary?.source ?? null,
    doctorReviewRequired: bundle.planSummary?.doctorReviewRequired ?? null,
    warnings: bundle.planSummary?.warnings ?? [],
    initialStageLabel: initial?.label ?? (initial ? `Stage ${initial.index}` : "Unavailable"),
    targetStageLabel: target?.label ?? (target ? `Stage ${target.index}` : "Unavailable"),
  };
}

/** Original vs target movement magnitudes from staged payloads (display only). */
export function buildSetupComparison(
  initial: ReviewStage | null | undefined,
  target: ReviewStage | null | undefined,
  limit = 12,
): SetupComparisonRow[] {
  if (!initial || !target) return [];
  const rows: SetupComparisonRow[] = [];
  for (const tooth of initial.teeth) {
    const key = reviewToothKey(tooth);
    const targetTooth = findToothByKey(target.teeth, key);
    const initialMovement = movementMagnitude(tooth.movement);
    const targetMovement = movementMagnitude(targetTooth?.movement);
    const delta = Math.abs(targetMovement - initialMovement);
    if (delta < 1e-8 && targetMovement < 1e-8) continue;
    rows.push({
      toothKey: key,
      label: formatToothIdentity(tooth),
      arch: tooth.arch,
      initialMovement,
      targetMovement,
      delta,
    });
  }
  return rows.sort((left, right) => right.delta - left.delta).slice(0, limit);
}

export function buildStagingSequence(stages: readonly ReviewStage[]): Array<{
  index: number;
  stageId: string;
  label: string;
  role: "Initial Position" | "Target Position" | "Intermediate";
  toothCount: number;
  validationStatus: string;
}> {
  return stages.map((stage, index) => ({
    index: stage.index,
    stageId: stage.stageId,
    label: stage.label ?? `Stage ${stage.index}`,
    role:
      index === 0
        ? "Initial Position"
        : index === stages.length - 1
          ? "Target Position"
          : "Intermediate",
    toothCount: stage.teeth.length,
    validationStatus: stage.validationStatus,
  }));
}

export function buildStageGoals(stage: ReviewStage | null | undefined): {
  label: string;
  type: string;
  findings: readonly string[];
} {
  if (!stage) {
    return { label: "Unavailable", type: "Unavailable", findings: [] };
  }
  return {
    label: stage.label ?? `Stage ${stage.index}`,
    type: stage.type ?? "Unavailable",
    findings: stage.validationFindings ?? stage.warnings ?? [],
  };
}

export function buildStageParameters(stage: ReviewStage | null | undefined): Array<{
  name: string;
  value: string;
}> {
  if (!stage) return [{ name: "Stage", value: "Unavailable" }];
  const rows = [
    { name: "Stage index", value: String(stage.index) },
    { name: "Stage id", value: stage.stageId },
    { name: "Tooth count", value: String(stage.teeth.length) },
    { name: "Validation", value: stage.validationStatus },
    { name: "Contacts", value: String(stage.contactCount) },
    { name: "Proximity", value: String(stage.proximityCount) },
    { name: "Collisions", value: String(stage.collisionCount) },
  ];
  if (stage.metadata) {
    for (const [key, value] of Object.entries(stage.metadata)) {
      rows.push({ name: key, value: String(value) });
    }
  }
  return rows;
}

export function buildPerToothMovementReview(
  teeth: readonly ReviewToothMesh[],
  limit = 16,
): Array<{
  label: string;
  arch: string;
  translation: number;
  rotation: number;
}> {
  return [...teeth]
    .map((tooth) => ({
      label: formatToothIdentity(tooth),
      arch: tooth.arch,
      translation: movementMagnitude(tooth.movement),
      rotation: Math.abs(tooth.movement.rotation),
    }))
    .sort((left, right) => right.translation - left.translation)
    .slice(0, limit);
}
