import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "./fixtureData";
import {
  applyFixtureMovementEdit,
  cancelFixtureEdits,
  recalculateFixtureBundle,
  resetAllFixtureEdits,
} from "./editing";

const movement = engineeringFixtureBundle.stages.at(-1)?.teeth[0].movement;

describe("doctor editing application seam", () => {
  it("applies one edit without mutating the original bundle", () => {
    const edited = applyFixtureMovementEdit(
      engineeringFixtureBundle,
      11,
      { ...movement!, translationX: 0.8 },
      "fixed-time",
    );
    expect(edited.proposalKind).toBe("doctor_edited");
    expect(edited.editHistory).toHaveLength(1);
    expect(edited.editHistory[0].reason).toBe("doctor_edit");
    expect(engineeringFixtureBundle.proposalKind).toBe("original_generated");
    expect(engineeringFixtureBundle.editHistory).toHaveLength(0);
  });

  it("cancels and resets all explicit edits", () => {
    const edited = applyFixtureMovementEdit(
      engineeringFixtureBundle,
      11,
      { ...movement!, translationX: 0.8 },
      "fixed-time",
    );
    expect(cancelFixtureEdits(engineeringFixtureBundle)).toBe(engineeringFixtureBundle);
    const reset = resetAllFixtureEdits(edited, "reset-time");
    expect(reset.stages.at(-1)?.teeth[0].movement).toEqual(movement);
    expect(reset.editHistory.length).toBeGreaterThan(1);
  });

  it("recalculates the edited bundle with a new lifecycle state and validation state", () => {
    const edited = applyFixtureMovementEdit(
      engineeringFixtureBundle,
      11,
      { ...movement!, rotation: 4 },
      "fixed-time",
    );
    const recalculated = recalculateFixtureBundle(edited);
    expect(recalculated.proposalKind).toBe("recalculated");
    expect(recalculated.editHistory).toEqual(edited.editHistory);
    expect(recalculated.stages.every((stage) => stage.validationStatus === "unavailable")).toBe(
      true,
    );
  });
});
