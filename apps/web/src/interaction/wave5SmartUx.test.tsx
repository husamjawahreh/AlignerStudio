import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CaseIntakeInspector } from "../components/CaseIntakePanel";
import {
  AdaptiveInspector,
  ContextualWorkspaceToolbar,
  DentalArchMap,
  PrimaryStatus,
} from "../components/workspace/ClinicalChrome";
import {
  buildContextualTools,
  buildDentalMapEntries,
  buildFeedbackModel,
  buildInspectorModel,
  buildSegmentationReviewModel,
  clinicalPayloadOmitsSyntheticGingiva,
  fdiIsAuthoritative,
  layoutBudget,
  matchWorkspaceShortcut,
  singleStatusSurface,
  toothReviewLabel,
} from "./model";
import { isKnownNextActionLabel, resolveNextAction, type NextActionInput } from "./nextAction";
import { dedupeNotice, splitToolbar, truthImpliesClinicalApproval, workflowOrientation } from "./smartUx";

const base = (patch: Partial<NextActionInput> = {}): NextActionInput => ({
  workspace: "case-intake",
  hasCase: false,
  upperReady: false,
  lowerReady: false,
  segmentationKind: "not_run",
  unresolvedIdentityCount: null,
  hasTreatment: false,
  stagingFreshness: null,
  validationFreshness: null,
  productionReachable: false,
  productionLimited: false,
  isBusy: false,
  stageStatus: null,
  canCancelProcessing: false,
  canRegenerateStaging: false,
  canRefreshValidation: false,
  ...patch,
});

describe("Wave 5 next-action resolver", () => {
  it("follows persisted evidence and never names an action the UI cannot run", () => {
    expect(resolveNextAction(base())?.label).toBe("Create Case");
    expect(resolveNextAction(base({ hasCase: true }))?.label).toBe("Import upper and lower scans");
    expect(resolveNextAction(base({ hasCase: true, upperReady: true }))?.label).toBe("Import lower scan");
    expect(
      resolveNextAction(
        base({
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "blocked_by_environment",
        }),
      )?.label,
    ).toBe("Review segmentation blocker");
    expect(
      resolveNextAction(
        base({
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "blocked_by_environment",
          workspace: "analysis",
        }),
      )?.id,
    ).not.toBe("retry-segmentation");
    expect(
      resolveNextAction(
        base({
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "not_run",
        }),
      )?.label,
    ).toBe("Review segmentation");
    expect(
      resolveNextAction(
        base({
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "failed",
        }),
      )?.label,
    ).toBe("Retry segmentation");
    expect(
      resolveNextAction(
        base({
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "requires_review",
          unresolvedIdentityCount: 2,
        }),
      )?.label,
    ).toBe("Review unresolved identities");
    expect(
      resolveNextAction(
        base({
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "not_available",
          workspace: "treatment-setup",
        }),
      )?.label,
    ).toBe("Review treatment setup dependency");
    expect(
      resolveNextAction(
        base({
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "not_available",
          workspace: "analysis",
        }),
      )?.label,
    ).toBe("Retry segmentation");
    expect(
      resolveNextAction(
        base({
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "real_model_inference",
          unresolvedIdentityCount: 0,
          hasTreatment: true,
          stagingFreshness: "stale",
          canRegenerateStaging: true,
          workspace: "staging",
        }),
      )?.label,
    ).toBe("Generate / Regenerate Staging");
    expect(
      resolveNextAction(
        base({
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "real_model_inference",
          unresolvedIdentityCount: 0,
          hasTreatment: true,
          validationFreshness: "stale",
          canRefreshValidation: true,
          workspace: "validation",
        }),
      )?.label,
    ).toBe("Dynamic staging refresh");
    expect(
      resolveNextAction(
        base({
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "real_model_inference",
          unresolvedIdentityCount: 0,
          hasTreatment: true,
          productionReachable: true,
          productionLimited: true,
          workspace: "production",
        }),
      )?.label,
    ).toBe("Review production limits");
    const busy = resolveNextAction(base({ hasCase: true, isBusy: true }));
    expect(busy).toBeNull();
    const cancel = resolveNextAction(
      base({ hasCase: true, stageStatus: "PROCESSING", canCancelProcessing: true, isBusy: true }),
    );
    expect(cancel?.label).toBe("Cancel processing");
    expect(cancel?.showInHeader).toBe(false);
    expect(cancel?.executable).toBe(true);
    for (const sample of [
      base(),
      base({ hasCase: true, upperReady: true, lowerReady: true, segmentationKind: "failed" }),
    ]) {
      const action = resolveNextAction(sample);
      expect(action).not.toBeNull();
      expect(isKnownNextActionLabel(action!.label)).toBe(true);
      expect(action!.label).not.toMatch(/IPR|attachment|approve|safe/i);
    }
  });

  it("resolves two thousand actions quickly without geometry", () => {
    const input = base({
      hasCase: true,
      upperReady: true,
      lowerReady: true,
      segmentationKind: "requires_review",
      unresolvedIdentityCount: 3,
    });
    const start = performance.now();
    for (let index = 0; index < 2000; index += 1) resolveNextAction(input);
    expect(performance.now() - start).toBeLessThan(50);
  });
});

describe("Wave 5 inspector, toolbar, and status", () => {
  const segmentation = (kindPatch: Parameters<typeof buildSegmentationReviewModel>[0]) =>
    buildSegmentationReviewModel(kindPatch);

  it("covers inspector variants without invented clinical controls", () => {
    const blocked = segmentation({
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
        runtime_blocker: "torch missing",
      },
      teeth: [],
    });
    const modes = [
      buildInspectorModel({
        minimized: false,
        patientReference: null,
        caseId: null,
        segmentation: blocked,
        selected: null,
        selectionCount: 0,
        confidence: null,
        treatmentAvailable: false,
      }).mode,
      buildInspectorModel({
        minimized: false,
        patientReference: "P",
        caseId: "c",
        segmentation: buildSegmentationReviewModel({ diagnostic: null, teeth: [] }),
        selected: null,
        selectionCount: 0,
        confidence: null,
        treatmentAvailable: false,
      }).mode,
      buildInspectorModel({
        minimized: false,
        patientReference: "P",
        caseId: "c",
        segmentation: blocked,
        selected: toothReviewLabel({ instanceId: 1, toothRef: "upper:instance:1", arch: "upper" }),
        selectionCount: 1,
        confidence: null,
        treatmentAvailable: false,
      }).mode,
      buildInspectorModel({
        minimized: false,
        patientReference: "P",
        caseId: "c",
        segmentation: blocked,
        selected: null,
        selectionCount: 2,
        confidence: null,
        treatmentAvailable: false,
        groupArches: "upper, lower",
        groupIdentity: "mixed",
      }).mode,
    ];
    expect(modes).toEqual(["blocked", "case", "tooth", "group"]);
    const processing = buildInspectorModel({
      minimized: false,
      patientReference: "P",
      caseId: "c",
      segmentation: buildSegmentationReviewModel({ diagnostic: null, teeth: [] }),
      selected: null,
      selectionCount: 0,
      confidence: null,
      treatmentAvailable: false,
      operation: "processing",
      phase: "SEGMENTING_LOWER",
    });
    expect(processing.mode).toBe("processing");
    expect(processing.actions).not.toContain("Move");
    const failed = buildInspectorModel({
      minimized: false,
      patientReference: "P",
      caseId: "c",
      segmentation: buildSegmentationReviewModel({
        diagnostic: {
          state: "segmentation_failed",
          source_kind: "uploaded_real_case",
          segmentation_runtime_ms: null,
          total_runtime_ms: 1,
          tooth_instance_count: 0,
          identification_confidence: null,
          identified_teeth: 0,
          uncertain_teeth: 0,
          unidentified_teeth: 0,
          validation_findings: [],
          failures: ["decoder stopped"],
          arch_analysis_available: false,
          notes: [],
        },
        teeth: [],
      }),
      selected: null,
      selectionCount: 0,
      confidence: null,
      treatmentAvailable: false,
      operation: "failed",
    });
    expect(failed.mode).toBe("failed");
    expect(failed.recovery?.retry).toMatch(/new job/i);
    expect(failed.actions.join(" ")).not.toMatch(/correct identity|mark missing/i);
    render(<AdaptiveInspector model={failed} minimized={false} onToggle={() => undefined} />);
    expect(screen.getByTestId("failure-recovery")).toHaveTextContent(/source scans/i);
    expect(screen.getByTestId("inspector-advanced")).toBeInTheDocument();
  });

  it("keeps one status surface and does not repeat a notice", () => {
    const feedback = buildFeedbackModel({
      stageStatus: "PROCESSING",
      userMessage: "Evaluating collisions and proximity",
      elapsedSeconds: 12,
      phase: "VALIDATING",
      segmentation: null,
    });
    expect(feedback.remainingEstimate).toBeNull();
    expect(feedback.progressMode).toBe("indeterminate");
    expect(feedback.benchmarkNote).toBeNull();
    expect(feedback.phaseLabel).toBe("Phase VALIDATING");
    const measured = buildFeedbackModel({
      stageStatus: "PROCESSING",
      serverProgress: 40,
      benchmarkSeconds: 90,
      segmentation: null,
    });
    expect(measured.progressMode).toBe("server-progress");
    expect(measured.benchmarkNote).toMatch(/not a guarantee/i);
    expect(measured.remainingEstimate).toBeNull();
    render(<PrimaryStatus feedback={feedback} />);
    expect(document.querySelectorAll("[data-status-surface='primary']")).toHaveLength(1);
    expect(dedupeNotice(feedback.whatHappened, feedback.whatHappened)).toBeNull();
    expect(dedupeNotice(feedback.whatHappened, "Export stored")).toBe("Export stored");
    render(
      <CaseIntakeInspector
        caseId="case-1"
        patientReference="P-1"
        caseStatus="created"
        archUploads={{
          upper: { filename: "u.stl", size: 10, state: "valid" },
          lower: { filename: "", size: 0, state: "empty" },
        }}
        processingStatus={null}
      />,
    );
    expect(document.querySelectorAll("[data-readiness-surface='primary']")).toHaveLength(1);
    expect(screen.queryAllByText("Processing")).toHaveLength(0);
  });

  it("prioritizes toolbar actions and hides non-functional clinical tools", () => {
    const built = buildContextualTools({
      workspace: "analysis",
      sceneAvailable: true,
      segmentationKind: "requires_review",
      selectionCount: 1,
      archMode: "both",
      isolateActive: false,
      labelMode: "selected",
      gingivaVisible: true,
      segmentationVisible: true,
      wireframe: false,
      movementVisible: false,
      targetVisible: false,
      treatmentAvailable: false,
      validationAvailable: false,
      canTransform: false,
    });
    const split = splitToolbar(built.tools);
    expect(split.visible.map((tool) => tool.id)).toContain("fit-selection");
    expect(split.visible.map((tool) => tool.id)).not.toContain("wireframe");
    expect(split.advanced.map((tool) => tool.id)).toContain("wireframe");
    expect(built.tools.some((tool) => tool.id === "measure")).toBe(false);
    render(
      <ContextualWorkspaceToolbar
        tools={split.visible}
        advanced={split.advanced}
        unavailable={built.unavailable}
        onTool={() => undefined}
      />,
    );
    expect(screen.getByTestId("tool-fit-case")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Measure" })).not.toBeInTheDocument();
    expect(screen.getByTestId("toolbar-unavailable")).toHaveTextContent("Measure");
    expect(screen.getByTestId("toolbar-advanced")).toHaveTextContent("Wireframe");
  });

  it("renders the dental map from persisted instances only", () => {
    const entries = buildDentalMapEntries([
      {
        instanceId: 0,
        toothRef: "upper:instance:0",
        arch: "upper",
        fdiNumber: 11,
        fixture: true,
        provenance: "fixture",
      },
    ]);
    render(
      <DentalArchMap
        entries={entries}
        kind="fixture_test_only"
        selectedKeys={["upper:instance:0"]}
        hoveredKey={null}
        onSelect={() => undefined}
        onHover={() => undefined}
      />,
    );
    expect(screen.getByTestId("dental-map-upper:instance:0")).toHaveAttribute("data-fixture", "true");
    expect(screen.getByTestId("dental-map-upper:instance:0")).not.toHaveTextContent("FDI");
    expect(screen.getByText(/not a missing tooth/i)).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(fdiIsAuthoritative(entries[0] ? {
      instanceId: 0,
      toothRef: entries[0].toothRef,
      fdiNumber: 11,
      fixture: true,
    } : { instanceId: 0 })).toBe(false);
    expect(clinicalPayloadOmitsSyntheticGingiva({ toothRef: "upper:instance:0" })).toBe(true);
  });

  it("standardizes truth language and workflow copy", () => {
    expect(truthImpliesClinicalApproval("verified")).toBe(false);
    expect(truthImpliesClinicalApproval("fixture")).toBe(false);
    expect(truthImpliesClinicalApproval("blocked_by_environment")).toBe(false);
    expect(truthImpliesClinicalApproval("not_available")).toBe(false);
    const orientation = workflowOrientation({
      stepLabel: "Analysis",
      blockReason: null,
      next: resolveNextAction(
        base({
          workspace: "analysis",
          hasCase: true,
          upperReady: true,
          lowerReady: true,
          segmentationKind: "blocked_by_environment",
        }),
      ),
    });
    expect(orientation.where).toBe("Analysis");
    expect(orientation.next).toMatch(/Review segmentation blocker/);
    expect(orientation.next).not.toMatch(/FDI \d+/);
  });

  it("keeps keyboard shortcuts and a dominant viewport at desktop widths", () => {
    expect(matchWorkspaceShortcut({ key: "Escape", metaKey: false, ctrlKey: false, shiftKey: false, altKey: false })).toBe(
      "clear",
    );
    const button = document.createElement("button");
    button.textContent = "Fit case";
    document.body.appendChild(button);
    button.focus();
    expect(document.activeElement).toBe(button);
    fireEvent.keyDown(button, { key: "Escape" });
    for (const size of [
      [1366, 768],
      [1600, 1000],
      [1280, 800],
    ] as const) {
      const budget = layoutBudget(size[0], size[1]);
      expect(budget.viewportDominant).toBe(true);
      expect(budget.pageScroll).toBe(false);
    }
    expect(singleStatusSurface(["primary"])).toBe(true);
    expect(singleStatusSurface(["primary", "primary"])).toBe(false);
  });
});
