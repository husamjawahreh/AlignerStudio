import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "./review/fixtureData";
import type { ReviewBundle, ReviewStage, ReviewToothMesh } from "./review/types";
import {
  buildPerToothMovementReview,
  buildSetupComparison,
  buildStageGoals,
  buildStageParameters,
  buildStagingSequence,
  buildTreatmentSetupSummary,
} from "./treatmentWorkflowPresentation";

function emptyBundle(): ReviewBundle {
  return {
    stages: [],
    provenance: "generated",
    fixture: false,
    realDataAvailable: false,
    unavailableReason: "no plan",
    proposalKind: "original_generated",
    editHistory: [],
    iprSites: [],
    attachmentSites: [],
  };
}

describe("Treatment workflow presentation", () => {
  it("marks setup unavailable without inventing alternatives", () => {
    const summary = buildTreatmentSetupSummary(emptyBundle());
    expect(summary.available).toBe(false);
    expect(summary.setupAlternativesLabel).toBe("Unavailable");
    expect(summary.planVersionLabel).toBe("Unavailable");
    expect(summary.movedToothCount).toBeNull();
  });

  it("summarizes plan versions and movement from existing planSummary only", () => {
    const bundle: ReviewBundle = {
      ...engineeringFixtureBundle,
      realDataAvailable: true,
      planSummary: {
        movedToothCount: 4,
        totalMovement: 1.25,
        notableConflicts: [],
        dataGaps: [],
        warnings: ["doctor review required"],
        source: "deterministic planner",
        doctorReviewRequired: true,
      },
    };
    const summary = buildTreatmentSetupSummary(bundle);
    expect(summary.available).toBe(true);
    expect(summary.setupAlternativesLabel).toBe("Single setup available");
    expect(summary.stageCount).toBe(bundle.stages.length);
    expect(summary.movedToothCount).toBe(4);
    expect(summary.totalMovement).toBe(1.25);
    expect(summary.planVersionLabel).toContain("original generated");
  });

  it("builds original vs target comparison without inventing teeth", () => {
    const initial = engineeringFixtureBundle.stages[0];
    const target = engineeringFixtureBundle.stages.at(-1)!;
    const rows = buildSetupComparison(initial, target);
    expect(rows.every((row) => row.toothKey.length > 0)).toBe(true);
    expect(buildSetupComparison(null, target)).toEqual([]);
  });

  it("labels movement sequence roles from stage order", () => {
    const sequence = buildStagingSequence(engineeringFixtureBundle.stages);
    expect(sequence[0]?.role).toBe("Initial Position");
    expect(sequence.at(-1)?.role).toBe("Target Position");
    if (sequence.length > 2) {
      expect(sequence[1]?.role).toBe("Intermediate");
    }
  });

  it("reports unavailable stage goals when no stage is selected", () => {
    expect(buildStageGoals(null).label).toBe("Unavailable");
    expect(buildStageParameters(null)[0]?.value).toBe("Unavailable");
  });

  it("surfaces stage parameters from existing stage fields only", () => {
    const stage: ReviewStage = {
      ...engineeringFixtureBundle.stages[0],
      label: "Macro 1",
      type: "macro",
      metadata: { cadence: "7d" },
    };
    const goals = buildStageGoals(stage);
    expect(goals.label).toBe("Macro 1");
    expect(goals.type).toBe("macro");
    const parameters = buildStageParameters(stage);
    expect(parameters.some((row) => row.name === "cadence" && row.value === "7d")).toBe(true);
  });

  it("orders per-tooth movement review by translation magnitude", () => {
    const teeth: ReviewToothMesh[] = [
      {
        ...engineeringFixtureBundle.stages[0].teeth[0],
        instanceId: 1,
        movement: {
          ...engineeringFixtureBundle.stages[0].teeth[0].movement,
          translationX: 0.1,
          translationY: 0,
          translationZ: 0,
        },
      },
      {
        ...engineeringFixtureBundle.stages[0].teeth[0],
        instanceId: 2,
        toothRef: "upper:instance:2",
        movement: {
          ...engineeringFixtureBundle.stages[0].teeth[0].movement,
          translationX: 1,
          translationY: 0,
          translationZ: 0,
        },
      },
    ];
    const rows = buildPerToothMovementReview(teeth);
    expect(rows[0]?.translation).toBeGreaterThanOrEqual(rows[1]?.translation ?? 0);
  });
});
