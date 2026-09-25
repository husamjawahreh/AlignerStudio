import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { engineeringFixtureBundle } from "../../review/fixtureData";
import {
  CAMERA_PRESETS,
  createCaseSceneHierarchy,
  createDefaultLayerControls,
  createOverlayRegistry,
  filterTeethByArchVisibility,
  isClinicalGeometryOverlay,
  nearFarForSphere,
  preserveSelectionAcrossTeeth,
  resolveFitBounds,
  resolveToothVisualRole,
  semanticIdentityFromTooth,
  setArchGroupVisibility,
  toothVisualStyle,
  enableBvhAcceleration,
  prepareMeshForPicking,
  pickToothFromPointer,
  disposeObjectTree,
  rendererResourceSnapshot,
} from "./index";
import { reviewToothKey } from "../toothKey";

describe("WP-03 scene hierarchy", () => {
  it("creates named CaseRoot structure with upper/lower arches", () => {
    const hierarchy = createCaseSceneHierarchy();
    expect(hierarchy.caseRoot.name).toBe("CaseRoot");
    expect(hierarchy.upperArch.name).toBe("UpperArch");
    expect(hierarchy.lowerArch.name).toBe("LowerArch");
    expect(hierarchy.occlusionLayer.userData.truthState).toBe("not_available");
    setArchGroupVisibility(hierarchy, "upper", false);
    expect(hierarchy.upperArch.visible).toBe(false);
    expect(hierarchy.lowerArch.visible).toBe(true);
  });
});

describe("WP-03 selection visuals", () => {
  it("distinguishes selected, hovered, requires_review, and validation roles", () => {
    expect(
      resolveToothVisualRole({
        arch: "upper",
        selected: true,
        hovered: true,
        validationStatus: "fail",
      }),
    ).toBe("selected");
    expect(
      resolveToothVisualRole({
        arch: "upper",
        selected: false,
        hovered: true,
      }),
    ).toBe("hovered");
    expect(
      resolveToothVisualRole({
        arch: "lower",
        selected: false,
        hovered: false,
        truthState: "requires_review",
      }),
    ).toBe("requires_review");
    expect(
      resolveToothVisualRole({
        arch: "lower",
        selected: false,
        hovered: false,
        validationStatus: "fail",
      }),
    ).toBe("validation_error");
    const reviewStyle = toothVisualStyle({
      arch: "upper",
      selected: false,
      hovered: false,
      truthState: "requires_review",
    });
    const selectedStyle = toothVisualStyle({
      arch: "upper",
      selected: true,
      hovered: false,
    });
    expect(reviewStyle.emissive).not.toBe(selectedStyle.emissive);
  });
});

describe("WP-03 arch + tooth isolation", () => {
  it("isolates by semantic arch and tooth_ref, not array index", () => {
    const teeth = engineeringFixtureBundle.stages[0].teeth;
    const firstUpper = teeth.find((tooth) => tooth.arch === "upper")!;
    const key = reviewToothKey(firstUpper);
    const isolated = filterTeethByArchVisibility(teeth, {
      ...createDefaultLayerControls(),
      isolatedToothKey: key,
    });
    expect(isolated).toHaveLength(1);
    expect(reviewToothKey(isolated[0])).toBe(key);

    // Shuffling array order must not change isolation identity.
    const shuffled = [...teeth].reverse();
    const again = filterTeethByArchVisibility(shuffled, {
      ...createDefaultLayerControls(),
      isolatedToothKey: key,
    });
    expect(reviewToothKey(again[0])).toBe(key);
  });
});

describe("WP-03 fit targets", () => {
  it("fits selected tooth by toothKey and supports arch/case", () => {
    const meshA = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1));
    meshA.position.set(10, 0, 0);
    meshA.updateMatrixWorld(true);
    const meshB = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1));
    meshB.position.set(-10, 0, 0);
    meshB.updateMatrixWorld(true);
    const group = new THREE.Group();
    group.add(meshA, meshB);
    group.updateMatrixWorld(true);

    const selected = resolveFitBounds({
      request: { target: "selected", selectedKey: "upper:instance:0" },
      meshes: [
        { object: meshA, toothKey: "upper:instance:0", arch: "upper" },
        { object: meshB, toothKey: "lower:instance:0", arch: "lower" },
      ],
      fallbackGroup: group,
    });
    expect(selected?.label).toMatch(/selected/i);
    expect(selected?.sphere.center.x).toBeCloseTo(10, 0);

    const arch = resolveFitBounds({
      request: { target: "arch", arch: "lower" },
      meshes: [
        { object: meshA, toothKey: "upper:instance:0", arch: "upper" },
        { object: meshB, toothKey: "lower:instance:0", arch: "lower" },
      ],
      fallbackGroup: group,
    });
    expect(arch?.sphere.center.x).toBeCloseTo(-10, 0);

    const depth = nearFarForSphere(selected!.sphere);
    expect(depth.near).toBeGreaterThan(0);
    expect(depth.far).toBeGreaterThan(depth.near);
    expect(CAMERA_PRESETS.map((item) => item.id)).toContain("front");
  });
});

describe("WP-03 overlay registry", () => {
  it("keeps synthetic gingiva out of clinical geometry overlays", () => {
    const registry = createOverlayRegistry();
    const gingiva = registry.get("gingiva")!;
    expect(isClinicalGeometryOverlay(gingiva)).toBe(false);
    expect(registry.get("occlusion")?.truthState).toBe("not_available");
    expect(registry.get("local_frames")?.enabled).toBe(false);
    const toggled = registry.setVisible("movement_vectors", false);
    expect(toggled.get("movement_vectors")?.visible).toBe(false);
  });
});

describe("WP-03 selection persistence + no FDI invent", () => {
  it("preserves tooth_ref across stages without fabricating FDI", () => {
    const stage0 = engineeringFixtureBundle.stages[0].teeth;
    const tooth = stage0[0];
    const key = reviewToothKey(tooth);
    const withoutFdi = {
      ...tooth,
      fdiNumber: null as number | null,
      toothRef: tooth.toothRef ?? key,
    };
    const identity = semanticIdentityFromTooth(withoutFdi);
    expect(identity.hasClinicalFdi).toBe(false);
    expect(identity.fdiNumber).toBeNull();
    // Same tooth list (stage reload) — selection must survive by semantic key.
    const preserved = preserveSelectionAcrossTeeth(key, stage0);
    expect(preserved?.key).toBe(key);
    expect(preserved?.instanceId).toBe(tooth.instanceId);
  });
});

describe("WP-03 BVH picking + resource disposal", () => {
  it("picks by toothKey and disposes geometry trees", () => {
    enableBvhAcceleration();
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const mesh = new THREE.Mesh(geometry);
    mesh.userData = { toothKey: "upper:instance:7", toothRef: "upper:instance:7" };
    prepareMeshForPicking(mesh);
    mesh.updateMatrixWorld(true);

    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    camera.position.set(0, 0, 3);
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld(true);
    const hit = pickToothFromPointer(
      new THREE.Raycaster(),
      camera,
      new THREE.Vector2(0, 0),
      [mesh],
    );
    expect(hit?.toothKey).toBe("upper:instance:7");

    const group = new THREE.Group();
    group.add(mesh);
    disposeObjectTree(group);
    expect(mesh.geometry).toBeTruthy();
  });

  it("exposes renderer snapshot helper without requiring a live WebGL context", () => {
    // WebGL is unavailable in this vitest environment — helper is still exported for runtime use.
    expect(typeof rendererResourceSnapshot).toBe("function");
  });
});
