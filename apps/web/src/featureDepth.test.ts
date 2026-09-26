import { describe, expect, it } from "vitest";
import { classifyFeatureDepth, featureById } from "./featureDepth";
import { resolveToolbar } from "./interaction/toolbar";

const blockedHost = classifyFeatureDepth({
  liveInferenceAvailable: false,
  hasStoredPlan: true,
  fixtureSegmentation: false,
  movementLimitsConfigured: false,
  iprValueSource: "centroid_distance",
  attachmentApproved: false,
  occlusionEvidence: false,
  clinicalAxesFromMeshPca: false,
  validationScorePresent: false,
});

describe("Wave 9 feature depth", () => {
  it("keeps segmentation blocked when live inference is unavailable", () => {
    expect(featureById(blockedHost, "segmentation").availability).toBe("blocked_by_environment");
    expect(featureById(blockedHost, "segmentation").reason).toMatch(/this computer/i);
  });

  it("treats tooth edits as geometric when no movement limits are configured", () => {
    const row = featureById(blockedHost, "tooth-edit");
    expect(row.availability).toBe("executable");
    expect(row.reason).toMatch(/No movement limits are configured/);
  });

  it("does not treat a centroid distance as an IPR prescription", () => {
    expect(featureById(blockedHost, "ipr").reason).toMatch(/not an IPR prescription/);
  });

  it("does not approve attachments or invent occlusion from crown-only data", () => {
    expect(featureById(blockedHost, "attachment").reason).toMatch(/not invented|review candidates/i);
    expect(featureById(blockedHost, "occlusion").availability).toBe("blocked_by_data");
  });

  it("rejects a validation score and a mesh-direction clinical axis", () => {
    const scored = classifyFeatureDepth({
      liveInferenceAvailable: false,
      hasStoredPlan: true,
      fixtureSegmentation: true,
      movementLimitsConfigured: false,
      iprValueSource: null,
      attachmentApproved: true,
      occlusionEvidence: false,
      clinicalAxesFromMeshPca: true,
      validationScorePresent: true,
    });
    expect(featureById(scored, "validation").reason).toMatch(/score is not/i);
    expect(featureById(scored, "occlusion").reason).toMatch(/not a clinical axis/);
    expect(featureById(scored, "attachment").reason).toMatch(/not produced/);
    expect(featureById(scored, "fixture-segmentation").availability).toBe("fixture_only");
  });

  it("offers move on Treatment Setup through the same edit stack", () => {
    const setup = resolveToolbar({
      workspace: "treatment-setup",
      hasCase: true,
      sceneAvailable: true,
      segmentationKind: "fixture_test_only",
      selectionCount: 1,
      groupIdentity: "same",
      archMode: "both",
      isolateActive: false,
      labelMode: "selected",
      gingivaVisible: false,
      segmentationVisible: true,
      wireframe: false,
      movementVisible: false,
      targetVisible: true,
      treatmentAvailable: true,
      targetGeometryExists: true,
      validationAvailable: true,
      validationFindingCount: null,
      stagingCount: 2,
      stagingStale: false,
      canTransform: true,
      canUndo: true,
      canRedo: false,
      canCancelProcessing: false,
      canRetrySegmentation: false,
      canRegenerateStaging: true,
      stageStatus: null,
      manipulationOwnedByToothToolbar: true,
    });
    expect(setup.withheld.find((item) => item.id === "move")?.reason).toMatch(/existing edit stack/);
    expect(setup.primary.find((item) => item.id === "undo")).toBeTruthy();
  });
});
