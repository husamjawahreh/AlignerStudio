/**
 * Wave 4 presentation contracts.
 * These tests lock visual policy. They do not claim clinical enamel, gingiva, or segmentation.
 */
import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  buildSegmentationReviewModel,
  clinicalPayloadOmitsSyntheticGingiva,
  fdiIsAuthoritative,
  toothReviewLabel,
  type CameraCommand,
} from "../interaction/model";
import { engineeringFixtureBundle } from "../review/fixtureData";
import { float32PositionsFromVertices } from "./geometryBuffers";
import { dentalMaterialProfiles, enamelProfileForArch, profileColor } from "./materialProfiles";
import {
  LABEL_DENSITY_CAP,
  nextLabelMode,
  resolveLabelVisibility,
} from "./presentation/labelPolicy";
import {
  INCREMENTAL_UPDATE_POLICY,
  ORDINARY_SELECTION_MOVES_CAMERA,
  RENDERING_PREPROCESS,
  SCENE_GRAPH_FACTORY,
  STUDIO_BACKGROUND,
  installDentalStudioLighting,
} from "./presentation/lighting";
import { resolveGingivaPresentation } from "./syntheticGingiva";
import {
  PRESENTATION_FIT_FILL,
  WORKSPACE_OVERLAY_CAPABILITIES,
  createCaseSceneHierarchy,
  createDefaultLayerControls,
  filterTeethByArchVisibility,
  framingDistanceFactor,
  stableViewDirection,
  measurementOverlayPresentation,
  resolveFitBounds,
  toothVisualStyle,
  validationOverlayPresentation,
} from "./workspace";

const baseLabel = {
  hovered: false,
  multiSelected: false,
  singleArchIsolated: false,
  visibleToothCount: 8,
};

describe("Wave 4 materials and selection", () => {
  it("uses one restrained enamel profile set", () => {
    const upper = dentalMaterialProfiles.enamelUpper;
    const lower = dentalMaterialProfiles.enamelLower;
    expect(upper.roughness).toBeGreaterThan(0.35);
    expect(lower.roughness).toBeGreaterThan(0.35);
    expect(Number(upper.metalness)).toBeLessThanOrEqual(0.03);
    expect(Number(upper.envMapIntensity)).toBeLessThan(0.7);
    expect(Number(dentalMaterialProfiles.enamelSelected.emissiveIntensity)).toBeLessThan(0.2);
    expect(profileColor(upper.color, 0)).not.toBe(profileColor(lower.color, 0));
    expect(enamelProfileForArch("upper")).toBe(upper);
    expect("vertices" in upper).toBe(false);
  });

  it("keeps hover lighter than selection and multi-selection in the same family", () => {
    const selected = toothVisualStyle({ arch: "upper", selected: true, hovered: false });
    const hover = toothVisualStyle({ arch: "upper", selected: false, hovered: true });
    const multi = toothVisualStyle({
      arch: "upper",
      selected: false,
      hovered: false,
      multiSelected: true,
    });
    const normal = toothVisualStyle({ arch: "upper", selected: false, hovered: false });
    expect(selected.role).toBe("selected");
    expect(hover.role).toBe("hovered");
    expect(multi.role).toBe("multi_selected");
    expect(selected.emissiveIntensity).toBeGreaterThan(multi.emissiveIntensity);
    expect(multi.emissiveIntensity).toBeGreaterThan(hover.emissiveIntensity);
    expect(hover.emissiveIntensity).toBeGreaterThan(normal.emissiveIntensity);
    expect(hover.color).toBe(normal.color);
    expect(selected.emissiveIntensity).toBeLessThan(0.2);
  });

  it("distinguishes current and target without an approval color", () => {
    const current = toothVisualStyle({ arch: "lower", selected: false, hovered: false });
    const target = toothVisualStyle({
      arch: "lower",
      selected: false,
      hovered: false,
      isTreatmentTarget: true,
    });
    expect(target.role).toBe("treatment_target");
    expect(target.color).not.toBe(current.color);
    expect(target.transparent).toBe(true);
    expect(target.opacity).toBeGreaterThan(0.5);
    expect(target.opacity).toBeLessThan(0.85);
    const targetColor = new THREE.Color(dentalMaterialProfiles.enamelTarget.color);
    expect(targetColor.g).toBeLessThan(0.95);
    expect(Math.abs(targetColor.g - targetColor.b)).toBeLessThan(0.12);
  });
});

describe("Wave 4 gingiva, labels, and identity", () => {
  it("keeps synthetic gingiva presentation-only and out of clinical payloads", () => {
    const teeth = engineeringFixtureBundle.stages[0]?.teeth ?? [];
    const meshes = resolveGingivaPresentation(teeth, null);
    expect(meshes.length).toBeGreaterThan(0);
    expect(meshes.every((mesh) => mesh.presentationOnly && mesh.source === "synthetic")).toBe(true);
    expect(dentalMaterialProfiles.gingivaVisualization.opacity).toBeGreaterThan(0.7);
    expect(dentalMaterialProfiles.gingivaVisualization.opacity).toBeLessThan(0.9);
    expect(clinicalPayloadOmitsSyntheticGingiva({ tooth_ref: "upper:instance:0" })).toBe(true);
    expect(clinicalPayloadOmitsSyntheticGingiva({ gingiva: meshes })).toBe(false);
  });

  it("shows priority labels and refuses invented FDI", () => {
    expect(resolveLabelVisibility({ ...baseLabel, mode: "selected", selected: true })).toBe(true);
    expect(resolveLabelVisibility({ ...baseLabel, mode: "selected", selected: false })).toBe(false);
    expect(resolveLabelVisibility({ ...baseLabel, mode: "off", selected: true })).toBe(false);
    expect(resolveLabelVisibility({ ...baseLabel, mode: "all", selected: false })).toBe(true);
    expect(
      resolveLabelVisibility({
        ...baseLabel,
        mode: "all",
        selected: false,
        visibleToothCount: LABEL_DENSITY_CAP + 1,
      }),
    ).toBe(false);
    expect(
      resolveLabelVisibility({
        ...baseLabel,
        mode: "arch",
        selected: false,
        singleArchIsolated: true,
      }),
    ).toBe(true);
    expect(
      resolveLabelVisibility({
        ...baseLabel,
        mode: "arch",
        selected: false,
        singleArchIsolated: false,
      }),
    ).toBe(false);
    expect(nextLabelMode("selected")).toBe("arch");

    const fixture = {
      instanceId: 0,
      toothRef: "upper:instance:0",
      fdiNumber: 11,
      arch: "upper" as const,
      planningMode: "clinical_fdi" as const,
      identificationStatus: "identified",
      provenance: "fixture",
      fixture: true,
    };
    expect(fdiIsAuthoritative(fixture)).toBe(false);
    expect(toothReviewLabel(fixture).text).toBe("upper:instance:0");
    expect(toothReviewLabel(fixture).unresolved).toBe(true);
    const authoritative = { ...fixture, fixture: false, experimental: false, provenance: "real" };
    expect(toothReviewLabel(authoritative).text).toBe("FDI 11");
  });

  it("filters arches without adding teeth", () => {
    const teeth = engineeringFixtureBundle.stages[0]?.teeth ?? [];
    const upper = filterTeethByArchVisibility(teeth, {
      ...createDefaultLayerControls(),
      isolatedArch: "upper",
    });
    expect(upper.length).toBeGreaterThan(0);
    expect(upper.every((tooth) => tooth.arch === "upper")).toBe(true);
    expect(upper.length).toBeLessThan(teeth.length);
  });
});

describe("Wave 4 truth states and camera", () => {
  it("does not present blocked segmentation as zero teeth", () => {
    const model = buildSegmentationReviewModel({
      diagnostic: {
        state: "blocked_by_environment",
        segmentation_truth_state: "blocked_by_environment",
        source_kind: "uploaded_real_case",
        runtime_blocker: "No NVIDIA driver, torch, or pointops.",
        segmentation_runtime_ms: null,
        total_runtime_ms: 1,
        tooth_instance_count: 0,
        identification_confidence: null,
        identified_teeth: 0,
        uncertain_teeth: 0,
        unidentified_teeth: 0,
        validation_findings: [],
        failures: [],
        arch_analysis_available: false,
        notes: [],
      },
      teeth: [],
    });
    expect(model.kind).toBe("blocked_by_environment");
    expect(model.instanceCountLabel).toBe("Not available");
    expect(model.headline).toMatch(/blocked/i);
  });

  it("marks fixture output as test-only", () => {
    const model = buildSegmentationReviewModel({
      diagnostic: {
        state: "identification_incomplete",
        source_kind: "validated_real_case",
        segmentation_runtime_ms: 1,
        total_runtime_ms: 1,
        tooth_instance_count: 1,
        identification_confidence: null,
        identified_teeth: 0,
        uncertain_teeth: 1,
        unidentified_teeth: 1,
        validation_findings: [],
        failures: [],
        arch_analysis_available: false,
        notes: [],
        provenance: "fixture",
        fixture: true,
      },
      teeth: [
        {
          instanceId: 0,
          toothRef: "upper:instance:0",
          arch: "upper",
          provenance: "fixture",
          fixture: true,
        },
      ],
    });
    expect(model.kind).toBe("fixture_test_only");
    expect(model.headline).toMatch(/fixture/i);
    expect(model.whatHappened).toMatch(/not live ToothInstanceNet/i);
  });

  it("refuses unavailable overlays and never treats absence as safe", () => {
    const validation = WORKSPACE_OVERLAY_CAPABILITIES.find((item) => item.kind === "validation");
    const measurement = WORKSPACE_OVERLAY_CAPABILITIES.find((item) => item.kind === "measurement");
    expect(validation?.available).toBe(false);
    expect(measurement?.available).toBe(false);
    const hidden = validationOverlayPresentation({
      capabilityAvailable: false,
      severity: null,
    });
    expect(hidden.draw).toBe(false);
    expect(hidden.impliesApproval).toBe(false);
    expect(hidden.reason).toMatch(/not a pass/i);
    const absentFinding = validationOverlayPresentation({
      capabilityAvailable: true,
      severity: "absent",
    });
    expect(absentFinding.draw).toBe(false);
    expect(absentFinding.impliesApproval).toBe(false);
    const fail = validationOverlayPresentation({ capabilityAvailable: true, severity: "fail" });
    expect(fail.draw).toBe(true);
    expect(fail.tone).toBe("fail");
    expect(fail.impliesApproval).toBe(false);
    const missingMeasure = measurementOverlayPresentation({
      capabilityAvailable: false,
      hasMeasurement: false,
      unit: null,
    });
    expect(missingMeasure.draw).toBe(false);
    expect(missingMeasure.unitLabel).toBeNull();
    const modelSpace = measurementOverlayPresentation({
      capabilityAvailable: true,
      hasMeasurement: true,
      unit: null,
    });
    expect(modelSpace.draw).toBe(true);
    expect(modelSpace.unitLabel).toMatch(/model-space/);
  });

  it("frames the subject inside the vertical field of view", () => {
    const fov = 42;
    for (const fill of Object.values(PRESENTATION_FIT_FILL)) {
      const factor = framingDistanceFactor(fov, fill);
      const angular = 2 * Math.atan(1 / factor) * (180 / Math.PI);
      expect(angular).toBeLessThan(fov * 0.92);
      expect(angular).toBeGreaterThan(fov * 0.55);
    }
    expect(PRESENTATION_FIT_FILL.selection).toBeGreaterThan(PRESENTATION_FIT_FILL.case);
    const occlusal = stableViewDirection(new THREE.Vector3(0, 1, 0));
    expect(Math.abs(occlusal.y)).toBeLessThan(0.98);
    expect(occlusal.length()).toBeCloseTo(1, 5);

    const meshA = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1));
    meshA.position.set(10, 0, 0);
    const meshB = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1));
    meshB.position.set(-10, 0, 0);
    meshB.visible = false;
    meshA.updateMatrixWorld(true);
    meshB.updateMatrixWorld(true);
    const group = new THREE.Group();
    group.add(meshA, meshB);
    const fitted = resolveFitBounds({
      request: { target: "case" },
      meshes: [
        { object: meshA, toothKey: "upper:instance:0", arch: "upper" },
        { object: meshB, toothKey: "lower:instance:0", arch: "lower" },
      ],
      fallbackGroup: group,
    });
    expect(fitted?.sphere.center.x).toBeCloseTo(10, 0);

    const commands: CameraCommand[] = [
      { type: "fit-case" },
      { type: "fit-arch", arch: "upper" },
      { type: "fit-selection", keys: ["upper:instance:0"] },
      { type: "preset", preset: "occlusal" },
      { type: "preset", preset: "front" },
      { type: "preset", preset: "right" },
      { type: "reset" },
    ];
    expect(commands.map((command) => command.type)).toContain("reset");
    expect(ORDINARY_SELECTION_MOVES_CAMERA).toBe(false);
  });
});

describe("Wave 4 scene integrity and incremental updates", () => {
  it("keeps a single case scene graph", () => {
    const hierarchy = createCaseSceneHierarchy();
    expect(SCENE_GRAPH_FACTORY).toBe("createCaseSceneHierarchy");
    expect(hierarchy.caseRoot.name).toBe("CaseRoot");
    const names = hierarchy.caseRoot.children.map((child) => child.name);
    expect(new Set(names).size).toBe(names.length);
    expect(names).toContain("UpperArch");
    expect(names).toContain("LowerArch");
    expect(names).toContain("TreatmentLayer");
    expect(names).toContain("ValidationLayer");
  });

  it("computes rendering normals on a copy and leaves source vertices unchanged", () => {
    const source: [number, number, number][] = [
      [0, 0, 0],
      [1, 0, 0],
      [0, 1, 0],
    ];
    const before = source.map((vertex) => [...vertex]);
    const copy = float32PositionsFromVertices(source);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(copy, 3));
    geometry.computeVertexNormals();
    expect(source).toEqual(before);
    expect(RENDERING_PREPROCESS.vertexNormals).toMatch(/copied/i);
    expect(geometry.getAttribute("normal").count).toBe(3);
  });

  it("resolves visual updates without rebuilding geometry", () => {
    const start = performance.now();
    for (let index = 0; index < 2000; index += 1) {
      toothVisualStyle({
        arch: index % 2 === 0 ? "upper" : "lower",
        selected: index % 5 === 0,
        hovered: index % 7 === 0,
        multiSelected: index % 11 === 0,
      });
      resolveLabelVisibility({
        mode: "selected",
        selected: index % 5 === 0,
        hovered: false,
        multiSelected: false,
        singleArchIsolated: false,
        visibleToothCount: 12,
      });
      framingDistanceFactor(42, PRESENTATION_FIT_FILL.case);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(80);
    expect(INCREMENTAL_UPDATE_POLICY.selection).toMatch(/material/);
    expect(INCREMENTAL_UPDATE_POLICY.archVisibility).toMatch(/visibility/);
    expect(INCREMENTAL_UPDATE_POLICY.labels).toMatch(/DOM/);

    const scene = new THREE.Scene();
    installDentalStudioLighting(scene);
    expect(scene.fog).toBeNull();
    expect((scene.background as THREE.Color).getHex()).toBe(STUDIO_BACKGROUND);
    const key = scene.getObjectByName("StudioKey");
    expect(key).toBeInstanceOf(THREE.DirectionalLight);
    expect((key as THREE.DirectionalLight).intensity).toBeLessThan(1.6);
    expect((key as THREE.DirectionalLight).intensity).toBeGreaterThan(0.8);
  });
});
