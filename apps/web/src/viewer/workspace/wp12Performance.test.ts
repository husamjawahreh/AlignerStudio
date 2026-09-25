/**
 * WP-12 performance probes — visibility toggles must not rebuild geometry/BVH.
 * Headless-safe (no WebGL). Measures filter application vs mesh rebuild cost.
 */

import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { engineeringFixtureBundle } from "../../review/fixtureData";
import { float32PositionsFromVertices, uint32IndicesFromFaces } from "../geometryBuffers";
import {
  createCaseSceneHierarchy,
  enableBvhAcceleration,
  prepareMeshForPicking,
  setArchGroupVisibility,
} from "./index";
import { reviewToothKey } from "../toothKey";

describe("WP-12 visibility without geometry rebuild", () => {
  it("applies arch/hide filters without recreating BufferGeometry or BVH", () => {
    const teeth = engineeringFixtureBundle.stages[0].teeth;
    enableBvhAcceleration();
    const hierarchy = createCaseSceneHierarchy();
    const records: Array<{
      mesh: THREE.Mesh;
      toothKey: string;
      arch: "upper" | "lower";
      instanceId: number;
      geometryUuid: string;
    }> = [];

    const buildMsStart = performance.now();
    for (const tooth of teeth) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute(
        "position",
        new THREE.Float32BufferAttribute(float32PositionsFromVertices(tooth.vertices), 3),
      );
      geometry.setIndex(uint32IndicesFromFaces(tooth.faces));
      geometry.computeVertexNormals();
      const mesh = new THREE.Mesh(geometry);
      const key = reviewToothKey(tooth);
      mesh.userData.toothKey = key;
      prepareMeshForPicking(mesh);
      if (tooth.arch === "upper") hierarchy.upperTeeth.add(mesh);
      else hierarchy.lowerTeeth.add(mesh);
      records.push({
        mesh,
        toothKey: key,
        arch: tooth.arch,
        instanceId: tooth.instanceId,
        geometryUuid: geometry.uuid,
      });
    }
    const buildMs = performance.now() - buildMsStart;

    const filterStart = performance.now();
    setArchGroupVisibility(hierarchy, "upper", false);
    setArchGroupVisibility(hierarchy, "lower", true);
    const hidden = new Set([teeth[0]?.instanceId].filter((v): v is number => v != null));
    for (const record of records) {
      const archVisible = record.arch === "upper" ? false : true;
      const toothVisible = archVisible && !hidden.has(record.instanceId);
      record.mesh.visible = toothVisible;
    }
    const filterMs = performance.now() - filterStart;

    // eslint-disable-next-line no-console
    console.log(
      "WP12_MEASURED",
      JSON.stringify({
        toothCount: teeth.length,
        buildMs,
        filterMs,
        upperVisible: hierarchy.upperArch.visible,
        lowerVisible: hierarchy.lowerArch.visible,
      }),
    );

    expect(filterMs).toBeLessThan(buildMs);
    expect(filterMs).toBeLessThan(50);
    for (const record of records) {
      expect(record.mesh.geometry.uuid).toBe(record.geometryUuid);
      expect(
        (record.mesh.geometry as THREE.BufferGeometry & { boundsTree?: unknown }).boundsTree,
      ).toBeTruthy();
    }
  });
});
