import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "../review/fixtureData";
import {
  findMatchingTooth,
  remainingMovementEndpoints,
  toothDisplayCentroid,
} from "./movementPresentation";
import { findToothByKey, reviewToothKey, toothMatchesKey } from "./toothKey";

describe("interaction tooth keys", () => {
  it("prefers toothRef, then FDI, then instance fallback", () => {
    expect(reviewToothKey({ instanceId: 7, toothRef: "upper:instance:7", fdiNumber: 11 })).toBe(
      "upper:instance:7",
    );
    expect(reviewToothKey({ instanceId: 11, toothRef: null, fdiNumber: 11 })).toBe("11");
    expect(reviewToothKey({ instanceId: 3, toothRef: null, fdiNumber: null })).toBe("instance:3");
  });

  it("matches legacy instance keys used by the viewer", () => {
    const tooth = { instanceId: 11, toothRef: null as string | null, fdiNumber: 11 };
    expect(toothMatchesKey(tooth, "11")).toBe(true);
    expect(toothMatchesKey(tooth, "instance:11")).toBe(true);
    expect(findToothByKey([tooth], "instance:11")?.fdiNumber).toBe(11);
  });
});

describe("movement presentation vectors", () => {
  it("draws remaining movement from current centroid to target centroid", () => {
    const current = engineeringFixtureBundle.stages[0]?.teeth[0];
    const target = engineeringFixtureBundle.stages.at(-1)?.teeth[0];
    expect(current && target).toBeTruthy();
    if (!current || !target) return;
    const endpoints = remainingMovementEndpoints(current, target);
    expect(endpoints).not.toBeNull();
    expect(endpoints?.start).toEqual(toothDisplayCentroid(current));
    expect(endpoints?.end).toEqual(toothDisplayCentroid(target));
  });

  it("does not invent a vector from movement.translation when poses match", () => {
    const tooth = engineeringFixtureBundle.stages.at(-1)?.teeth[0];
    expect(tooth).toBeTruthy();
    if (!tooth) return;
    expect(remainingMovementEndpoints(tooth, tooth)).toBeNull();
  });

  it("matches target teeth without mutating source stage data", () => {
    const stage = engineeringFixtureBundle.stages[0];
    const target = engineeringFixtureBundle.stages.at(-1);
    expect(stage && target).toBeTruthy();
    if (!stage || !target) return;
    const before = structuredClone(stage.teeth);
    const matched = findMatchingTooth(target.teeth, stage.teeth[0]!);
    expect(matched?.fdiNumber).toBe(stage.teeth[0]?.fdiNumber);
    expect(stage.teeth).toEqual(before);
  });
});
