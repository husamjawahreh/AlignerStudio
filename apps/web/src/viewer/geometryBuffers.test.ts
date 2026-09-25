import { describe, expect, it } from "vitest";
import { float32PositionsFromVertices, uint32IndicesFromFaces } from "./geometryBuffers";

describe("geometryBuffers", () => {
  it("packs vertices without flatMap intermediate arrays", () => {
    const positions = float32PositionsFromVertices([
      [1, 2, 3],
      [4, 5, 6],
    ]);
    expect(Array.from(positions)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it("packs faces contiguously", () => {
    expect(uint32IndicesFromFaces([[0, 1, 2], [2, 3, 0]])).toEqual([0, 1, 2, 2, 3, 0]);
  });
});
