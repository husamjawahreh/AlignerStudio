import { describe, expect, it } from "vitest";
import { engineeringFixtureBundle } from "../../review/fixtureData";
import {
  createCadWorkspaceLayerRegistry,
  createDefaultLayerControls,
  filterTeethByArchVisibility,
  preserveSelectionAcrossTeeth,
  semanticIdentityFromTooth,
  identitiesEqual,
  CAMERA_PRESETS,
  overlayCapability,
  validateGeometryWorkerRequest,
  GEOMETRY_WORKER_FORBIDDEN_FIELDS,
  enableBvhAcceleration,
  isBvhAccelerationEnabled,
  pickToothFromPointer,
} from "./index";
import * as THREE from "three";

describe("3D workspace arch layers", () => {
  it("isolates upper/lower without inventing teeth", () => {
    const teeth = engineeringFixtureBundle.stages[0].teeth;
    const upperOnly = filterTeethByArchVisibility(teeth, {
      ...createDefaultLayerControls(),
      isolatedArch: "upper",
    });
    expect(upperOnly.every((tooth) => tooth.arch === "upper")).toBe(true);
    expect(upperOnly.length).toBeGreaterThan(0);
    expect(upperOnly.length).toBeLessThan(teeth.length);
  });

  it("marks future overlays as unavailable with reasons", () => {
    const layers = createCadWorkspaceLayerRegistry();
    expect(layers.ipr.available).toBe(false);
    expect(layers.measurements.available).toBe(false);
    expect(layers.measurements.reason).toMatch(/not available/i);
  });
});

describe("3D selection identity", () => {
  it("preserves semantic identity across stages without fabricating FDI", () => {
    const stage0 = engineeringFixtureBundle.stages[0].teeth;
    const stageN = engineeringFixtureBundle.stages.at(-1)!.teeth;
    const first = stage0.find((tooth) => tooth.toothRef) ?? stage0[0];
    const identity = semanticIdentityFromTooth(first);
    expect(identity.hasClinicalFdi).toBe(first.fdiNumber != null);

    const preserved = preserveSelectionAcrossTeeth(identity.key, stageN);
    expect(preserved).not.toBeNull();
    expect(identitiesEqual(identity, preserved)).toBe(true);
  });

  it("does not invent FDI when tooth has none", () => {
    const tooth = {
      ...engineeringFixtureBundle.stages[0].teeth[0],
      fdiNumber: null,
      toothRef: "upper:instance:99",
      semanticLabel: 1,
    };
    const identity = semanticIdentityFromTooth(tooth);
    expect(identity.fdiNumber).toBeNull();
    expect(identity.hasClinicalFdi).toBe(false);
    expect(identity.key).toBe("upper:instance:99");
  });
});

describe("camera / overlay / worker architecture", () => {
  it("exposes camera presets and honest overlay availability", () => {
    expect(CAMERA_PRESETS.length).toBeGreaterThanOrEqual(6);
    expect(overlayCapability("gizmo").available).toBe(true);
    expect(overlayCapability("orientation_cube").available).toBe(true);
    expect(overlayCapability("local_frames").available).toBe(false);
  });

  it("validates worker requests without clinical fields", () => {
    expect(
      validateGeometryWorkerRequest({
        operation: "compute_bounds",
        positions: new Float32Array(9),
        requestId: "r1",
      }),
    ).toBeNull();
    expect(GEOMETRY_WORKER_FORBIDDEN_FIELDS).toContain("fdiNumber");
  });
});

describe("BVH picking foundation", () => {
  it("enables BVH acceleration and picks by existing toothKey only", () => {
    expect(enableBvhAcceleration()).toBe(true);
    expect(isBvhAccelerationEnabled()).toBe(true);

    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const mesh = new THREE.Mesh(geometry);
    mesh.userData = { toothKey: "upper:instance:1" };
    mesh.updateMatrixWorld(true);

    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    camera.position.set(0, 0, 3);
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld(true);

    const raycaster = new THREE.Raycaster();
    const hit = pickToothFromPointer(raycaster, camera, new THREE.Vector2(0, 0), [mesh]);
    expect(hit?.toothKey).toBe("upper:instance:1");
  });

  it("ignores presentation-only meshes", () => {
    enableBvhAcceleration();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1));
    mesh.userData = { presentationOnly: true, toothKey: "should-not-pick" };
    mesh.updateMatrixWorld(true);
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    camera.position.set(0, 0, 3);
    camera.lookAt(0, 0, 0);
    const hit = pickToothFromPointer(
      new THREE.Raycaster(),
      camera,
      new THREE.Vector2(0, 0),
      [mesh],
    );
    expect(hit).toBeNull();
  });
});
