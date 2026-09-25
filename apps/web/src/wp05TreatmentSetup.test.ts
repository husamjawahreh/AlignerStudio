import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "./review/fixtureData";
import { buildTreatmentSetupSummary } from "./treatmentWorkflowPresentation";

describe("WP-05 Treatment Setup 2.0 presentation", () => {
  it("summarizes fixture setup without inventing clinical approval", () => {
    const summary = buildTreatmentSetupSummary(engineeringFixtureBundle);
    expect(summary.proposalKind).toContain("original");
    expect(summary.doctorReviewRequired).not.toBe(false);
    // Fixture bundles mark realDataAvailable=false; availability follows that honesty flag.
    expect(typeof summary.available).toBe("boolean");
    expect(summary.available).toBe(false);
  });

  it("treats missing treatmentSetup contract as optional FE field", () => {
    expect(engineeringFixtureBundle.treatmentSetup).toBeUndefined();
    expect(engineeringFixtureBundle.planId).toBeUndefined();
  });
});
