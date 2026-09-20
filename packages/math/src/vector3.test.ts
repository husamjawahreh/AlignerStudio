import { describe, expect, it } from "vitest";
import { addVectors, lerpVectors, scaleVector, subtractVectors, vectorLength } from "./vector3";

describe("vector3 helpers", () => {
  it("adds vectors component-wise", () => {
    expect(addVectors({ x: 1, y: 2, z: 3 }, { x: 4, y: 5, z: 6 })).toEqual({ x: 5, y: 7, z: 9 });
  });

  it("subtracts vectors component-wise", () => {
    expect(subtractVectors({ x: 5, y: 7, z: 9 }, { x: 1, y: 2, z: 3 })).toEqual({
      x: 4,
      y: 5,
      z: 6,
    });
  });

  it("scales a vector", () => {
    expect(scaleVector({ x: 1, y: -2, z: 3 }, 2)).toEqual({ x: 2, y: -4, z: 6 });
  });

  it("computes vector length", () => {
    expect(vectorLength({ x: 3, y: 4, z: 0 })).toBe(5);
  });

  it("lerps between vectors and clamps t", () => {
    const a = { x: 0, y: 0, z: 0 };
    const b = { x: 10, y: 0, z: 0 };
    expect(lerpVectors(a, b, 0.5)).toEqual({ x: 5, y: 0, z: 0 });
    expect(lerpVectors(a, b, 2)).toEqual(b);
    expect(lerpVectors(a, b, -1)).toEqual(a);
  });
});
