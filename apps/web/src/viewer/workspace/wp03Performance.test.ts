/**
 * WP-03 performance probe — measures local presentation work on real-case-sized
 * tooth lists. Does not invent clinical data or claim GPU inference.
 *
 * Run: npx vitest run src/viewer/workspace/wp03Performance.test.ts
 */

import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { engineeringFixtureBundle } from "../../review/fixtureData";
import { float32PositionsFromVertices, uint32IndicesFromFaces } from "../geometryBuffers";
import { createCaseSceneHierarchy, enableBvhAcceleration, prepareMeshForPicking } from "./index";
import { reviewToothKey } from "../toothKey";

describe("WP-03 performance probe (fixture-sized presentation)", () => {
  it("measures hierarchy + buffer upload + BVH prepare (not invented)", () => {
    const teeth = engineeringFixtureBundle.stages[0].teeth;
    enableBvhAcceleration();

    const t0 = performance.now();
    const hierarchy = createCaseSceneHierarchy();
    const tHierarchy = performance.now();

    const meshes: THREE.Mesh[] = [];
    for (const tooth of teeth) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(float32PositionsFromVertices(tooth.vertices), 3),
      );
      geometry.setIndex(uint32IndicesFromFaces(tooth.faces));
      geometry.computeVertexNormals();
      const mesh = new THREE.Mesh(geometry);
      mesh.userData.toothKey = reviewToothKey(tooth);
      prepareMeshForPicking(mesh);
      if (tooth.arch === "upper") hierarchy.upperTeeth.add(mesh);
      else hierarchy.lowerTeeth.add(mesh);
      meshes.push(mesh);
    }
    const tMeshes = performance.now();

    const bounds = new THREE.Box3().setFromObject(hierarchy.allContent);
    const tBounds = performance.now();

    const measured = {
      toothCount: teeth.length,
      hierarchyMs: tHierarchy - t0,
      meshBuildAndBvhMs: tMeshes - tHierarchy,
      boundsMs: tBounds - tMeshes,
      totalMs: tBounds - t0,
      boundsEmpty: bounds.isEmpty(),
    };
    // eslint-disable-next-line no-console
    console.log("WP03_MEASURED", JSON.stringify(measured));

    expect(measured.toothCount).toBeGreaterThan(0);
    expect(measured.boundsEmpty).toBe(false);
    expect(measured.totalMs).toBeGreaterThanOrEqual(0);
    expect(meshes).toHaveLength(teeth.length);
  });
});
