import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "../review/fixtureData";
import {
  isUsableRealGingiva,
  resolveGingivaPresentation,
  type RealGingivaMeshInput,
} from "./syntheticGingiva";

const fixtureTeeth = engineeringFixtureBundle.stages[0]?.teeth ?? [];

describe("gingiva presentation (P1)", () => {
  it("builds a synthetic continuous envelope when real gingiva is absent", () => {
    const meshes = resolveGingivaPresentation(fixtureTeeth, null);
    expect(meshes.length).toBeGreaterThan(0);
    for (const mesh of meshes) {
      expect(mesh.source).toBe("synthetic");
      expect(mesh.presentationOnly).toBe(true);
      expect(mesh.faces.length).toBeGreaterThan(24);
      expect(mesh.vertices.length).toBeGreaterThan(24);
    }
    expect(meshes.some((mesh) => mesh.arch === "upper")).toBe(true);
    expect(meshes.some((mesh) => mesh.arch === "lower")).toBe(true);
  });

  it("prefers usable real gingiva geometry over synthetic", () => {
    const real: RealGingivaMeshInput[] = [
      {
        arch: "upper",
        vertices: Array.from({ length: 30 }, (_, index) => [index * 0.1, 1, 0] as [number, number, number]),
        faces: Array.from({ length: 20 }, (_, index) => [0, index + 1, ((index + 2) % 28) + 1] as [number, number, number]),
      },
    ];
    expect(isUsableRealGingiva(real)).toBe(true);
    const meshes = resolveGingivaPresentation(fixtureTeeth, real);
    expect(meshes).toHaveLength(1);
    expect(meshes[0]?.source).toBe("real");
    expect(meshes[0]?.presentationOnly).toBe(true);
    expect(meshes[0]?.vertices).toHaveLength(30);
  });

  it("rejects undersized real gingiva and falls back to synthetic", () => {
    const unusable: RealGingivaMeshInput[] = [
      {
        arch: "upper",
        vertices: [
          [0, 0, 0],
          [1, 0, 0],
          [0, 1, 0],
        ],
        faces: [[0, 1, 2]],
      },
    ];
    expect(isUsableRealGingiva(unusable)).toBe(false);
    const meshes = resolveGingivaPresentation(fixtureTeeth, unusable);
    expect(meshes.every((mesh) => mesh.source === "synthetic")).toBe(true);
  });

  it("does not mutate source tooth geometry or clinical movement fields", () => {
    const before = structuredClone(fixtureTeeth);
    void resolveGingivaPresentation(fixtureTeeth, null);
    expect(fixtureTeeth).toEqual(before);
    for (let index = 0; index < fixtureTeeth.length; index += 1) {
      expect(fixtureTeeth[index]?.movement).toEqual(before[index]?.movement);
      expect(fixtureTeeth[index]?.vertices).toEqual(before[index]?.vertices);
      expect(fixtureTeeth[index]?.faces).toEqual(before[index]?.faces);
    }
  });

  it("avoids a single rectangular slab (varied radii + multi-band topology)", () => {
    const upper = resolveGingivaPresentation(fixtureTeeth, null).find((mesh) => mesh.arch === "upper");
    expect(upper).toBeTruthy();
    if (!upper) return;
    const center = upper.vertices.reduce(
      (sum, vertex) => [sum[0] + vertex[0], sum[1] + vertex[1], sum[2] + vertex[2]] as [number, number, number],
      [0, 0, 0] as [number, number, number],
    );
    const mean: [number, number, number] = [
      center[0] / upper.vertices.length,
      center[1] / upper.vertices.length,
      center[2] / upper.vertices.length,
    ];
    const radii = upper.vertices.map((vertex) =>
      Math.hypot(vertex[0] - mean[0], vertex[1] - mean[1], vertex[2] - mean[2]),
    );
    const minR = Math.min(...radii);
    const maxR = Math.max(...radii);
    expect(maxR - minR).toBeGreaterThan(0.05);
    expect(upper.faces.length).toBeGreaterThan(40);
  });

  it("respects independent arch inclusion for the toggleable layer", () => {
    const upperOnly = resolveGingivaPresentation(fixtureTeeth, null, {
      includeUpper: true,
      includeLower: false,
    });
    expect(upperOnly.every((mesh) => mesh.arch === "upper")).toBe(true);
    const lowerOnly = resolveGingivaPresentation(fixtureTeeth, null, {
      includeUpper: false,
      includeLower: true,
    });
    expect(lowerOnly.every((mesh) => mesh.arch === "lower")).toBe(true);
  });
});
