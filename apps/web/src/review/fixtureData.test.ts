import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "./fixtureData";

describe("engineering fixture review data", () => {
  it("is visibly marked as fixture and has deterministic stages", () => {
    expect(engineeringFixtureBundle.fixture).toBe(true);
    expect(engineeringFixtureBundle.provenance).toBe("fixture");
    expect(engineeringFixtureBundle.stages.map((stage) => stage.stageId)).toEqual([
      "fixture-stage-0",
      "fixture-stage-1",
      "fixture-stage-2",
    ]);
    expect(engineeringFixtureBundle.realDataAvailable).toBe(false);
  });
});
