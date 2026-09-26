import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AdaptiveInspector } from "../components/workspace/ClinicalChrome";
import { ACTION_OWNERSHIP, ownersFor } from "./actionOwnership";
import { buildInspectorModel, buildSegmentationReviewModel, toothReviewLabel } from "./model";
import { resolveToolbar, type ToolbarMachineInput } from "./toolbar";

function toolbar(patch: Partial<ToolbarMachineInput>): ToolbarMachineInput {
  return {
    workspace: "analysis",
    hasCase: true,
    sceneAvailable: false,
    segmentationKind: "not_run",
    selectionCount: 0,
    groupIdentity: null,
    archMode: "both",
    isolateActive: false,
    labelMode: "off",
    gingivaVisible: false,
    segmentationVisible: true,
    wireframe: false,
    movementVisible: false,
    targetVisible: false,
    treatmentAvailable: false,
    targetGeometryExists: false,
    validationAvailable: false,
    validationFindingCount: null,
    stagingCount: 0,
    stagingStale: false,
    canTransform: false,
    canUndo: false,
    canRedo: false,
    canCancelProcessing: false,
    canRetrySegmentation: false,
    canRegenerateStaging: false,
    stageStatus: null,
    ...patch,
  };
}

const baseSeg = buildSegmentationReviewModel({ diagnostic: null, teeth: [] });

function model(extra: Partial<Parameters<typeof buildInspectorModel>[0]> = {}) {
  return buildInspectorModel({
    minimized: false,
    patientReference: "P",
    caseId: "case-1",
    segmentation: baseSeg,
    selected: null,
    selectionCount: 0,
    confidence: null,
    treatmentAvailable: false,
    ...extra,
  });
}

describe("Wave 10 adaptive inspector", () => {
  it("keeps no-selection, one-tooth, and multi-tooth inspectors distinct", () => {
    const tooth = toothReviewLabel({
      instanceId: 0,
      toothRef: "upper:instance:0",
      arch: "upper",
      fdiNumber: null,
      fixture: true,
    });
    const none = model({ workspace: "treatment-setup", treatmentAvailable: true, facts: { version: "abc123" } });
    const one = model({
      workspace: "treatment-setup",
      treatmentAvailable: true,
      selected: tooth,
      selectionCount: 1,
      transform: {
        current: "0.20 mm X · 0.00 mm Y · 0.00 mm Z · 0.00° rot",
        target: "1.00 mm X · 0.00 mm Y · 0.00 mm Z · 0.00° rot",
        locked: false,
        excluded: false,
        editable: true,
      },
    });
    const many = model({
      workspace: "treatment-setup",
      selectionCount: 2,
      groupArches: "upper",
      groupIdentity: "same",
      groupEditable: "all",
    });
    expect(none.mode).toBe("treatment-setup");
    expect(one.mode).toBe("tooth");
    expect(many.mode).toBe("group");
    expect(one.rows.find((row) => row.label === "tooth_ref")?.value).toBe("upper:instance:0");
    expect(one.rows.find((row) => row.label === "FDI")?.value).toBe("Not resolved");
    expect(one.rows.find((row) => row.label === "Target")?.value).toMatch(/1\.00 mm X/);
    expect(many.rows.some((row) => row.label === "Current" || row.label === "Target")).toBe(false);
    expect(many.rows.find((row) => row.label === "Editable")?.value).toMatch(/All selected/);
    expect(one.actions).toEqual([]);
    expect(many.actions).toEqual([]);
  });

  it("omits a target row when no target is stored and does not invent a zero measurement", () => {
    const tooth = toothReviewLabel({ instanceId: 1, toothRef: "lower:instance:1", arch: "lower" });
    const selected = model({
      selected: tooth,
      selectionCount: 1,
      confidence: null,
      transform: { current: "0.00 mm X · 0.00 mm Y · 0.00 mm Z · 0.00° rot", target: null, locked: null, excluded: null, editable: null },
    });
    expect(selected.rows.some((row) => row.label === "Target")).toBe(false);
    expect(selected.rows.some((row) => row.label === "Confidence")).toBe(false);
  });

  it("switches workspace inspectors without a shared permanent panel", () => {
    const modes = (["treatment-setup", "staging", "refinement", "validation", "production", "analysis"] as const).map(
      (workspace) =>
        model({
          workspace,
          treatmentAvailable: true,
          facts: {
            stageCount: 3,
            stageIndex: 1,
            freshness: "current",
            findingCount: 2,
            unavailableChecks: 1,
            truth: "requires_review",
            source: "stored-stage",
            editCount: 1,
          },
        }).mode,
    );
    expect(modes).toEqual(["treatment-setup", "staging", "refinement", "validation", "production", "analysis"]);
    const staging = model({
      workspace: "staging",
      treatmentAvailable: true,
      facts: { stageCount: 3, stageIndex: 1, freshness: "stale" },
    });
    expect(staging.limitations.join(" ")).toMatch(/not clinically optimized/i);
    expect(staging.actions).toEqual([]);
    const validation = model({
      workspace: "validation",
      facts: { findingCount: 2, unavailableChecks: 4, truth: "requires_review" },
    });
    expect(validation.limitations.join(" ")).toMatch(/no score/i);
    expect(validation.limitations.join(" ")).not.toMatch(/safe %|clinical approval score/i);
    const production = model({ workspace: "production", facts: { source: "stage", truth: "requires_review" } });
    expect(production.limitations.join(" ")).toMatch(/not claimed/i);
  });

  it("keeps processing, blocked, failed, cancelled, and interrupted truthful and distinct", () => {
    const processing = model({
      operation: "processing",
      phase: "SEGMENTING_LOWER",
      elapsedLabel: "Elapsed 4s",
      selected: toothReviewLabel({ instanceId: 1, toothRef: "upper:instance:1", arch: "upper" }),
      selectionCount: 1,
    });
    expect(processing.mode).toBe("processing");
    expect(processing.rows.find((row) => row.label === "Progress")?.value).toMatch(/Indeterminate/);
    expect(processing.limitations.join(" ")).toMatch(/does not invent a percent or an ETA/);
    expect(processing.rows.some((row) => row.label === "tooth_ref")).toBe(false);

    const withServer = model({ operation: "processing", serverProgressLabel: "Server reported 40" });
    expect(withServer.rows.find((row) => row.label === "Progress")?.value).toBe("Server reported 40");

    const blocked = model({
      segmentation: buildSegmentationReviewModel({
        diagnostic: {
          state: "blocked_by_environment",
          source_kind: "uploaded_real_case",
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
          runtime_blocker: "pointops missing",
        },
        teeth: [],
      }),
    });
    expect(blocked.mode).toBe("blocked");
    expect(blocked.actions).not.toContain("Retry segmentation");
    expect(blocked.rows.find((row) => row.label === "Retry")?.value).toMatch(/Not offered/);

    const failed = model({ operation: "failed", failureMessage: "decoder stopped" });
    const cancelled = model({ operation: "cancelled" });
    const interrupted = model({ operation: "interrupted" });
    expect([failed.mode, cancelled.mode, interrupted.mode]).toEqual(["failed", "cancelled", "interrupted"]);
    expect(failed.rows.find((row) => row.label === "Failure")?.value).toBe("decoder stopped");
    expect(failed.recovery?.retry).toMatch(/new job/i);
    expect(cancelled.rows.find((row) => row.label === "Distinct from")?.value).toMatch(/Not a failure/);
    expect(interrupted.rows.find((row) => row.label === "Distinct from")?.value).toMatch(/Not a cancellation/);
    expect(cancelled.recovery?.retry).toMatch(/no mid-stage resume/i);
    expect(interrupted.recovery?.retry).toMatch(/does not resume mid-stage/i);
    render(<AdaptiveInspector model={failed} minimized={false} onToggle={() => undefined} />);
    expect(screen.getByTestId("inspector-failure")).toHaveTextContent("decoder stopped");
    expect(screen.getByTestId("inspector-advanced")).toBeInTheDocument();
  });

  it("shows requires-review and unavailable without a workspace override hiding them", () => {
    const review = model({
      segmentation: buildSegmentationReviewModel({
        diagnostic: {
          state: "identification_incomplete",
          source_kind: "validated_real_case",
          segmentation_runtime_ms: null,
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
        teeth: [],
      }),
    });
    expect(review.mode).toBe("requires_review");
    const fixtureSegmentation = buildSegmentationReviewModel({
      diagnostic: {
        state: "identification_incomplete",
        source_kind: "validated_real_case",
        segmentation_runtime_ms: null,
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
      teeth: [],
    });
    expect(model({ workspace: "analysis", segmentation: fixtureSegmentation }).mode).toBe("requires_review");
    expect(
      model({ workspace: "treatment-setup", treatmentAvailable: true, segmentation: fixtureSegmentation }).mode,
    ).toBe("treatment-setup");
    const unavailable = model({
      workspace: "analysis",
      segmentation: buildSegmentationReviewModel({
        diagnostic: {
          state: "model_unavailable",
          source_kind: "uploaded_real_case",
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
          segmentation_truth_state: "not_available",
        },
        teeth: [],
      }),
    });
    expect(unavailable.mode).toBe("unavailable");
    expect(unavailable.limitations.join(" ")).toMatch(/not a count of zero teeth/i);
  });

  it("gives every audited action one owner", () => {
    const actions = ACTION_OWNERSHIP.map((row) => row.action);
    expect(new Set(actions).size).toBe(actions.length);
    for (const action of actions) {
      expect(ownersFor(action)).toHaveLength(1);
    }
    expect(ownersFor("remaining-time")).toEqual(["processing-overlay"]);
    expect(ownersFor("move-rotate")).toEqual(["tooth-toolbar"]);
    expect(ownersFor("numeric-edit-lock-exclude-apply-reset-undo-redo")).toEqual(["inspector"]);
    expect(ownersFor("scan-preparation")).toEqual(["left-step-form"]);
  });

  it("shows preparation status in the inspector without preparation buttons", () => {
    const built = model({
      workspace: "case-intake",
      facts: { preparation: "upper PREPARED" },
    });
    expect(built.actions).toEqual([]);
    expect(built.rows.find((row) => row.label === "Preparation")?.value).toBe("upper PREPARED");
    expect(built.limitations.join(" ")).toMatch(/not clinical segmentation/i);
    render(<AdaptiveInspector model={built} minimized={false} onToggle={() => undefined} />);
    expect(screen.getByTestId("inspector-preparation").textContent).toContain("upper PREPARED");
    expect(screen.queryByRole("button", { name: /Rotate 90/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Apply trim/i })).toBeNull();
  });

  it("shows a preparation job in the inspector without preparation buttons", () => {
    const built = model({
      workspace: "case-intake",
      facts: { preparation: "upper PREPARED", preparationJob: "upper orient running 50%" },
    });
    expect(built.actions).toEqual([]);
    render(<AdaptiveInspector model={built} minimized={false} onToggle={() => undefined} />);
    expect(screen.getByTestId("inspector-preparation-job").textContent).toContain("orient running");
    expect(screen.queryByRole("button", { name: /Rotate 90/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Cancel job/i })).toBeNull();
  });

  it("shows segmentation status in the inspector without segmentation buttons", () => {
    const built = model({
      workspace: "case-intake",
      facts: {
        segmentation: "upper ENVIRONMENT_BLOCKED",
        segmentationIdentity: "NOT_ESTABLISHED",
      },
    });
    expect(built.actions).toEqual([]);
    render(<AdaptiveInspector model={built} minimized={false} onToggle={() => undefined} />);
    expect(screen.getByTestId("inspector-segmentation").textContent).toContain("ENVIRONMENT_BLOCKED");
    expect(screen.getByTestId("inspector-segmentation-identity").textContent).toContain(
      "NOT_ESTABLISHED",
    );
    expect(screen.queryByRole("button", { name: /Start segmentation/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Accept candidate/i })).toBeNull();
  });

  it("keeps undo on the inspector when a tooth edit is open and retry on the toolbar after cancel", () => {
    const editing = resolveToolbar(
      toolbar({
        workspace: "treatment-setup",
        sceneAvailable: true,
        segmentationKind: "fixture_test_only",
        selectionCount: 1,
        canUndo: true,
        canRedo: true,
        treatmentAvailable: true,
        commitOwnedByInspector: true,
        manipulationOwnedByToothToolbar: true,
      }),
    );
    expect(editing.primary.find((item) => item.id === "undo")).toBeUndefined();
    expect(editing.primary.find((item) => item.id === "redo")).toBeUndefined();

    const cancelled = resolveToolbar(
      toolbar({ stageStatus: "CANCELLED", canRetrySegmentation: true }),
    );
    expect(cancelled.context).toBe("cancelled");
    expect(cancelled.primary.find((item) => item.id === "retry-segmentation")?.reason).toMatch(/cancelled/i);

    const interrupted = resolveToolbar(
      toolbar({ stageStatus: "INTERRUPTED", canRetrySegmentation: true }),
    );
    expect(interrupted.context).toBe("interrupted");
    expect(interrupted.primary.find((item) => item.id === "retry-segmentation")?.reason).toMatch(/does not resume/i);

    const blocked = resolveToolbar(
      toolbar({ segmentationKind: "blocked_by_environment", canRetrySegmentation: true }),
    );
    expect(blocked.primary.find((item) => item.id === "retry-segmentation")).toBeUndefined();
  });

  it("resolves inspector context far below a frame budget and does not return geometry", () => {
    const tooth = toothReviewLabel({ instanceId: 0, toothRef: "upper:instance:0", arch: "upper" });
    const inputs = [
      model({ workspace: "staging" }),
      model({ selected: tooth, selectionCount: 1, workspace: "refinement" }),
      model({ selectionCount: 3, groupEditable: "mixed", groupArches: "upper, lower" }),
      model({ operation: "processing", phase: "preparation" }),
    ];
    const start = performance.now();
    let last = inputs[0];
    for (let index = 0; index < 2000; index += 1) {
      last = buildInspectorModel({
        minimized: false,
        patientReference: "P",
        caseId: "case-1",
        segmentation: baseSeg,
        selected: index % 2 === 0 ? tooth : null,
        selectionCount: index % 3,
        confidence: null,
        treatmentAvailable: true,
        workspace: index % 2 === 0 ? "treatment-setup" : "validation",
        operation: index % 5 === 0 ? "processing" : null,
      });
    }
    const elapsed = performance.now() - start;
    expect(elapsed / 2000).toBeLessThan(1);
    expect(JSON.stringify(last)).not.toMatch(/vertices|faces|bvh/i);
    expect(inputs.map((item) => item.mode).join(",")).toMatch(/staging/);
  });
});
