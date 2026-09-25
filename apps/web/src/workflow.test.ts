import { describe, expect, it } from "vitest";
import {
  WORKFLOW_DEFINITIONS,
  buildWorkflowActions,
  buildWorkflowSteps,
  workflowPlanToken,
} from "./workflow";

describe("P2 clinical-CAD workflow", () => {
  it("exposes the Master Plan v2.1 sequence and labels literally", () => {
    expect(WORKFLOW_DEFINITIONS.map((step) => step.planToken)).toEqual([
      "CASE INTAKE",
      "ANALYSIS",
      "TREATMENT SETUP",
      "STAGING",
      "REFINEMENT",
      "VALIDATION",
      "PRODUCTION",
    ]);
    expect(WORKFLOW_DEFINITIONS.map((step) => step.label)).toEqual([
      "Case Intake",
      "Analysis",
      "Treatment Setup",
      "Staging",
      "Refinement",
      "Validation",
      "Production",
    ]);
    expect(WORKFLOW_DEFINITIONS).toHaveLength(7);
  });

  it("marks the active step as current and blocks downstream work until data is ready", () => {
    const steps = buildWorkflowSteps({
      activeStep: "case-intake",
      hasCase: false,
      bothArchesValid: false,
      hasSegmentation: false,
      hasTreatment: false,
      editCount: 0,
      hasValidation: false,
    });
    expect(steps.find((step) => step.id === "case-intake")?.status).toBe("current");
    expect(steps.find((step) => step.id === "analysis")?.status).toBe("blocked");
    expect(steps.find((step) => step.id === "staging")?.status).toBe("blocked");
    expect(steps.find((step) => step.id === "production")?.status).toBe("blocked");
  });

  it("unlocks analysis when both arches are valid and treatment when segmentation exists", () => {
    const ready = buildWorkflowSteps({
      activeStep: "analysis",
      hasCase: true,
      bothArchesValid: true,
      hasSegmentation: false,
      hasTreatment: false,
      editCount: 0,
      hasValidation: false,
    });
    expect(ready.find((step) => step.id === "case-intake")?.status).toBe("complete");
    expect(ready.find((step) => step.id === "analysis")?.status).toBe("current");
    expect(ready.find((step) => step.id === "treatment-setup")?.status).toBe("ready");

    const treated = buildWorkflowSteps({
      activeStep: "staging",
      hasCase: true,
      bothArchesValid: true,
      hasSegmentation: true,
      hasTreatment: true,
      editCount: 0,
      hasValidation: false,
    });
    expect(treated.find((step) => step.id === "staging")?.status).toBe("current");
    expect(treated.find((step) => step.id === "refinement")?.status).toBe("ready");
    expect(treated.find((step) => step.id === "production")?.status).toBe("ready");
  });

  it("provides contextual actions using Production terminology", () => {
    const actions = buildWorkflowActions({
      activeStep: "production",
      hasCase: true,
      bothArchesValid: true,
      hasSegmentation: true,
      hasTreatment: true,
      isBusy: false,
    });
    expect(actions.some((action) => action.label === "Export Package")).toBe(true);
    expect(workflowPlanToken("treatment-setup")).toBe("TREATMENT SETUP");

    const setupActions = buildWorkflowActions({
      activeStep: "treatment-setup",
      hasCase: true,
      bothArchesValid: true,
      hasSegmentation: true,
      hasTreatment: false,
      isBusy: false,
    });
    expect(setupActions.some((action) => action.label === "Create Treatment Plan")).toBe(true);
  });
});
