import { describe, expect, it } from "vitest";
import {
  nextActionOperation,
  operationStartsLongWork,
  resolveNextAction,
  type NextActionInput,
} from "./interaction/nextAction";
import {
  resolveWorkflow,
  resolveWorkflowNavigation,
  workflowStepFromHistory,
  type WorkflowEvidence,
  type WorkflowStepId,
} from "./workflow";

function evidence(overrides: Partial<WorkflowEvidence> = {}): WorkflowEvidence {
  return {
    activeStep: "case-intake",
    hasCase: false,
    upperReady: false,
    lowerReady: false,
    segmentationKind: "not_run",
    hasTreatment: false,
    hasTarget: false,
    stagingFreshness: null,
    stagingCount: 0,
    validationFreshness: null,
    hasValidationRun: false,
    productionReachable: false,
    productionLimited: true,
    editCount: 0,
    isBusy: false,
    stageStatus: null,
    canCancelProcessing: false,
    canRegenerateStaging: false,
    canRefreshValidation: false,
    unresolvedIdentityCount: null,
    ...overrides,
  };
}

function nextInput(value: WorkflowEvidence): NextActionInput {
  return {
    workspace: value.activeStep,
    hasCase: value.hasCase,
    upperReady: value.upperReady,
    lowerReady: value.lowerReady,
    segmentationKind: value.segmentationKind,
    unresolvedIdentityCount: value.unresolvedIdentityCount,
    hasTreatment: value.hasTreatment,
    stagingFreshness: value.stagingFreshness,
    validationFreshness: value.validationFreshness,
    productionReachable: value.productionReachable,
    productionLimited: value.productionLimited,
    isBusy: value.isBusy,
    stageStatus: value.stageStatus,
    canCancelProcessing: value.canCancelProcessing,
    canRegenerateStaging: value.canRegenerateStaging,
    canRefreshValidation: value.canRefreshValidation,
  };
}

describe("Wave 7 workflow resolver", () => {
  it("keeps one canonical next action across the resolver and resolveNextAction", () => {
    const samples = [
      evidence(),
      evidence({ hasCase: true, activeStep: "case-intake" }),
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "blocked_by_environment",
        activeStep: "analysis",
      }),
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "failed",
        activeStep: "analysis",
      }),
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "fixture_test_only",
        unresolvedIdentityCount: 2,
        activeStep: "analysis",
      }),
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "real_model_inference",
        unresolvedIdentityCount: 0,
        hasTreatment: true,
        hasTarget: true,
        stagingFreshness: "stale",
        stagingCount: 3,
        canRegenerateStaging: true,
        activeStep: "staging",
      }),
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "real_model_inference",
        unresolvedIdentityCount: 0,
        hasTreatment: true,
        hasTarget: true,
        stagingFreshness: "current",
        stagingCount: 4,
        validationFreshness: "stale",
        hasValidationRun: true,
        canRefreshValidation: true,
        productionReachable: true,
        activeStep: "validation",
      }),
    ];
    for (const sample of samples) {
      const workflow = resolveWorkflow(sample);
      const direct = resolveNextAction(nextInput(sample));
      expect(workflow.nextAction?.id ?? null).toBe(direct?.id ?? null);
      const labels = new Set(workflow.steps.map((step) => step.nextAction?.id ?? null));
      expect(labels.size).toBe(1);
      expect([...labels][0]).toBe(direct?.id ?? null);
    }
  });

  it("does not complete analysis without real segmentation evidence", () => {
    const blocked = resolveWorkflow(
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "blocked_by_environment",
        activeStep: "analysis",
      }),
    );
    const analysis = blocked.steps.find((step) => step.id === "analysis");
    expect(analysis?.state).toBe("blocked");
    expect(analysis?.satisfied).toBe(false);
    expect(analysis?.reason).toMatch(/not zero teeth/i);
    expect(analysis?.emptyState.missing).toMatch(/computer/i);

    const fixture = resolveWorkflow(
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "fixture_test_only",
        activeStep: "analysis",
      }),
    );
    expect(fixture.steps.find((step) => step.id === "analysis")?.state).toBe("requires_review");
    expect(fixture.steps.find((step) => step.id === "analysis")?.satisfied).toBe(false);
    expect(fixture.steps.find((step) => step.id === "analysis")?.reason).toMatch(/test-only/i);
  });

  it("keeps treatment setup from claiming a plan when segmentation is unavailable", () => {
    const workflow = resolveWorkflow(
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "blocked_by_environment",
        activeStep: "treatment-setup",
      }),
    );
    const setup = workflow.steps.find((step) => step.id === "treatment-setup");
    expect(setup?.state).toBe("unavailable");
    expect(setup?.navigationAllowed).toBe(true);
    expect(setup?.emptyState.missing).toBe("Treatment target");
    expect(setup?.emptyState.now).toMatch(/does not create a plan/i);
    expect(workflow.nextAction?.id).not.toBe("create-treatment-plan");
  });

  it("marks staging stale and validation stale without calling them complete", () => {
    const staging = resolveWorkflow(
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "real_model_inference",
        hasTreatment: true,
        hasTarget: true,
        stagingFreshness: "stale",
        stagingCount: 5,
        activeStep: "staging",
        canRegenerateStaging: true,
      }),
    );
    expect(staging.steps.find((step) => step.id === "staging")?.state).toBe("stale");
    expect(staging.nextAction?.id).toBe("regenerate-staging");

    const validation = resolveWorkflow(
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "real_model_inference",
        hasTreatment: true,
        hasTarget: true,
        stagingFreshness: "current",
        stagingCount: 5,
        validationFreshness: "stale",
        hasValidationRun: true,
        activeStep: "validation",
        canRefreshValidation: true,
        productionReachable: true,
      }),
    );
    expect(validation.steps.find((step) => step.id === "validation")?.state).toBe("stale");
    expect(validation.nextAction?.id).toBe("refresh-validation");
    expect(validation.steps.find((step) => step.id === "validation")?.emptyState.now).toMatch(/does not refresh/i);
  });

  it("keeps production incomplete while manufacturing is limited", () => {
    const workflow = resolveWorkflow(
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "real_model_inference",
        hasTreatment: true,
        hasTarget: true,
        stagingFreshness: "current",
        stagingCount: 2,
        validationFreshness: "current",
        hasValidationRun: true,
        productionReachable: true,
        productionLimited: true,
        activeStep: "production",
      }),
    );
    const production = workflow.steps.find((step) => step.id === "production");
    expect(production?.satisfied).toBe(false);
    expect(production?.state).toBe("requires_review");
    expect(production?.emptyState.now).toMatch(/not treat export as a finished appliance/i);
  });

  it("navigates without starting long work", () => {
    const workflow = resolveWorkflow(
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "not_run",
        activeStep: "case-intake",
      }),
    );
    const analysis = resolveWorkflowNavigation(workflow.steps, "analysis");
    expect(analysis.intent).toBe("enter");
    expect(analysis.operation).toBe("navigate");
    expect(operationStartsLongWork(nextActionOperation("review-segmentation"))).toBe(true);
    expect(operationStartsLongWork("navigate")).toBe(false);
    expect(nextActionOperation("open-treatment-plan")).toBe("navigate");
    expect(nextActionOperation("create-treatment-plan")).toBe("compute");

    const blockedFuture = resolveWorkflow(
      evidence({ hasCase: false, activeStep: "case-intake" }),
    );
    const denied = resolveWorkflowNavigation(blockedFuture.steps, "analysis");
    expect(denied.intent).toBe("explain");
    expect(denied.showDependency).toBe(true);
    expect(denied.operation).toBe("inspect");

    const review = resolveWorkflowNavigation(workflow.steps, "case-intake");
    expect(review.intent).toBe("stay");
  });

  it("reviews a completed earlier step and explains a step that cannot be opened", () => {
    const workflow = resolveWorkflow(
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "real_model_inference",
        unresolvedIdentityCount: 0,
        hasTreatment: true,
        hasTarget: true,
        stagingFreshness: "current",
        stagingCount: 3,
        activeStep: "staging",
      }),
    );
    expect(resolveWorkflowNavigation(workflow.steps, "case-intake").intent).toBe("review");
    expect(resolveWorkflowNavigation(workflow.steps, "staging").intent).toBe("stay");
    const failed = resolveWorkflow(
      evidence({
        hasCase: true,
        upperReady: true,
        lowerReady: true,
        segmentationKind: "failed",
        activeStep: "case-intake",
      }),
    );
    const enterFailed = resolveWorkflowNavigation(failed.steps, "analysis");
    expect(enterFailed.intent).toBe("enter");
    expect(enterFailed.showDependency).toBe(true);
    expect(failed.steps.find((step) => step.id === "analysis")?.state).toBe("failed");
  });

  it("restores a workflow step from history state and ignores unknown values", () => {
    expect(workflowStepFromHistory({ workflowStep: "validation" })).toBe("validation");
    expect(workflowStepFromHistory({ workflowStep: "launch" })).toBeNull();
    expect(workflowStepFromHistory(null)).toBeNull();
  });

  it("gives every step an id, dependency, completion condition, and empty state", () => {
    const workflow = resolveWorkflow(evidence({ hasCase: true, upperReady: true, lowerReady: false }));
    const ids: WorkflowStepId[] = [
      "case-intake",
      "analysis",
      "treatment-setup",
      "staging",
      "refinement",
      "validation",
      "production",
    ];
    expect(workflow.steps.map((step) => step.id)).toEqual(ids);
    for (const step of workflow.steps) {
      expect(step.dependency.length).toBeGreaterThan(0);
      expect(step.completionCondition.length).toBeGreaterThan(0);
      expect(step.emptyState.missing.length).toBeGreaterThan(0);
      expect(step.emptyState.why.length).toBeGreaterThan(0);
      expect(step.emptyState.now.length).toBeGreaterThan(0);
      expect(step.label).not.toMatch(/pipeline|backend|DTO|artifact/i);
    }
  });

  it("resolves workflow and next action without walking geometry", () => {
    const sample = evidence({
      hasCase: true,
      upperReady: true,
      lowerReady: true,
      segmentationKind: "real_model_inference",
      unresolvedIdentityCount: 0,
      hasTreatment: true,
      hasTarget: true,
      stagingFreshness: "current",
      stagingCount: 12,
      validationFreshness: "current",
      hasValidationRun: true,
      productionReachable: true,
      productionLimited: true,
      activeStep: "refinement",
    });
    const started = performance.now();
    for (let index = 0; index < 2000; index += 1) {
      resolveWorkflow(sample);
      resolveNextAction(nextInput(sample));
    }
    const elapsed = performance.now() - started;
    expect(elapsed).toBeLessThan(250);
  });
});
