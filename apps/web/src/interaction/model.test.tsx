import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { PipelineDiagnostic } from "../api/client";
import { engineeringFixtureBundle } from "../review/fixtureData";
import { resolveGingivaPresentation } from "../viewer/syntheticGingiva";
import {
  AdaptiveInspector,
  ContextualWorkspaceToolbar,
  DentalArchMap,
  SegmentationReviewStrip,
} from "../components/workspace/ClinicalChrome";
import {
  buildContextualTools,
  buildDentalMapEntries,
  buildFeedbackModel,
  buildInspectorModel,
  buildSegmentationReviewModel,
  clinicalPayloadOmitsSyntheticGingiva,
  deleteShortcutEffect,
  fdiIsAuthoritative,
  headerNextAction,
  isTextEntryTarget,
  layoutBudget,
  matchWorkspaceShortcut,
  shortcutChangesClinicalState,
  singleStatusSurface,
  toothReviewLabel,
  workflowBlockReason,
} from "./model";

function diagnostic(partial: Partial<PipelineDiagnostic>): PipelineDiagnostic {
  return {
    state: "planning_unavailable",
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
    ...partial,
  };
}

describe("Wave 3 segmentation review truth", () => {
  it("reports blocked environment without a zero-tooth success", () => {
    const model = buildSegmentationReviewModel({
      diagnostic: diagnostic({
        state: "blocked_by_environment",
        segmentation_truth_state: "blocked_by_environment",
        runtime_blocker: "No NVIDIA driver, torch, or pointops.",
        tooth_instance_count: 0,
      }),
      teeth: [],
    });
    expect(model.kind).toBe("blocked_by_environment");
    expect(model.instanceCountLabel).toBe("Not available");
    expect(model.runtimeBlocker).toMatch(/NVIDIA/);
    expect(model.missingToothStatement).toBe("Identity/data not established");
    expect(model.confidenceLabel).toBeNull();
    expect(model.provenanceLabel).not.toMatch(/real-model inference/i);
  });

  it("does not present fixture output as live inference or authoritative FDI", () => {
    const tooth = {
      instanceId: 0,
      toothRef: "upper:instance:0",
      fdiNumber: 11,
      arch: "upper" as const,
      planningMode: "clinical_fdi" as const,
      identificationStatus: "identified",
      provenance: "fixture" as const,
      fixture: true,
      confidence: 0.99,
    };
    expect(fdiIsAuthoritative(tooth)).toBe(false);
    expect(toothReviewLabel(tooth).text).toBe("upper:instance:0");
    const model = buildSegmentationReviewModel({
      diagnostic: diagnostic({
        state: "identification_incomplete",
        provenance: "fixture",
        fixture: true,
        identification_confidence: 0.8,
        tooth_instance_count: 1,
      }),
      teeth: [tooth],
    });
    expect(model.kind).toBe("fixture_test_only");
    expect(model.confidenceLabel).toBeNull();
    expect(model.unresolvedIdentityLabel).toBe("1 unresolved");
  });

  it("shows FDI only from authoritative non-fixture evidence", () => {
    const tooth = {
      instanceId: 2,
      toothRef: "lower:instance:2",
      fdiNumber: 31,
      arch: "lower" as const,
      planningMode: "clinical_fdi" as const,
      identificationStatus: "identified",
      provenance: "real" as const,
      fixture: false,
      experimental: false,
    };
    expect(fdiIsAuthoritative(tooth)).toBe(true);
    expect(toothReviewLabel(tooth).text).toBe("FDI 31");
    const model = buildSegmentationReviewModel({
      diagnostic: diagnostic({
        state: "planning_ready",
        provenance: "real",
        fixture: false,
        identification_confidence: 0.91,
      }),
      teeth: [tooth],
    });
    expect(model.kind).toBe("real_model_inference");
    expect(model.confidenceLabel).toBe("0.910");
  });

  it("keeps failed and not-available distinct from an empty arch", () => {
    const failed = buildSegmentationReviewModel({
      diagnostic: diagnostic({ state: "segmentation_failed", failures: ["checkpoint missing"] }),
      teeth: [],
    });
    const missing = buildSegmentationReviewModel({
      diagnostic: diagnostic({ state: "model_unavailable", failures: ["weights absent"] }),
      teeth: [],
    });
    expect(failed.kind).toBe("failed");
    expect(missing.kind).toBe("not_available");
    expect(failed.instanceCountLabel).toBe("Not available");
    expect(missing.instanceCountLabel).toBe("Not available");
  });
});

describe("Wave 3 selection, map, toolbar, inspector, keyboard, camera layout", () => {
  it("synchronizes map entries by tooth_ref and keeps unresolved distinct", () => {
    const entries = buildDentalMapEntries([
      {
        instanceId: 0,
        toothRef: "upper:instance:0",
        arch: "upper",
        fdiNumber: null,
      },
    ]);
    render(
      <DentalArchMap
        entries={entries}
        kind="requires_review"
        selectedKeys={["upper:instance:0"]}
        hoveredKey="upper:instance:0"
        onSelect={() => undefined}
        onHover={() => undefined}
      />,
    );
    const item = screen.getByTestId("dental-map-upper:instance:0");
    expect(item).toHaveAttribute("aria-selected", "true");
    expect(item.className).toMatch(/is-unresolved/);
    expect(item).toHaveTextContent("upper:instance:0");
    expect(item).not.toHaveTextContent("FDI");
  });

  it("does not render a zero-tooth map for a blocked segmentation", () => {
    render(
      <DentalArchMap
        entries={[]}
        kind="blocked_by_environment"
        selectedKeys={[]}
        hoveredKey={null}
        onSelect={() => undefined}
        onHover={() => undefined}
      />,
    );
    expect(screen.getByTestId("dental-arch-map")).toHaveAttribute("data-map-state", "unavailable");
    expect(screen.getByTestId("dental-map-unavailable")).toHaveTextContent(/not zero teeth/i);
  });

  it("selects from the map with the additive modifier", () => {
    const calls: boolean[] = [];
    render(
      <DentalArchMap
        entries={buildDentalMapEntries([
          { instanceId: 1, toothRef: "lower:instance:1", arch: "lower" },
        ])}
        kind="requires_review"
        selectedKeys={[]}
        hoveredKey={null}
        onSelect={(_ref, additive) => calls.push(additive)}
        onHover={() => undefined}
      />,
    );
    fireEvent.click(screen.getByTestId("dental-map-lower:instance:1"), { shiftKey: true });
    expect(calls).toEqual([true]);
  });

  it("builds contextual tools and hides non-functional clinical tools", () => {
    const blocked = buildContextualTools({
      workspace: "analysis",
      sceneAvailable: true,
      segmentationKind: "blocked_by_environment",
      selectionCount: 0,
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
    expect(blocked.tools.some((tool) => tool.id === "fit-case")).toBe(true);
    expect(blocked.tools.some((tool) => tool.id === "isolate")).toBe(false);
    expect(blocked.tools.some((tool) => tool.id === "measure")).toBe(false);
    expect(blocked.unavailable.some((note) => note.id === "measure")).toBe(true);
    const selected = buildContextualTools({
      ...{
        workspace: "analysis" as const,
        sceneAvailable: true,
        segmentationKind: "requires_review" as const,
        selectionCount: 1,
        archMode: "upper" as const,
        isolateActive: false,
        labelMode: "off",
        gingivaVisible: false,
        segmentationVisible: true,
        wireframe: false,
        movementVisible: false,
        targetVisible: false,
        treatmentAvailable: false,
        validationAvailable: false,
        canTransform: false,
      },
    });
    expect(selected.tools.find((tool) => tool.id === "arch-upper")?.active).toBe(true);
    expect(selected.tools.find((tool) => tool.id === "fit-selection")?.shortcut).toBe("F");
  });

  it("renders toolbar availability in the title and not as a fake measure button", () => {
    const { tools, unavailable } = buildContextualTools({
      workspace: "analysis",
      sceneAvailable: true,
      segmentationKind: "not_run",
      selectionCount: 0,
      archMode: "both",
      isolateActive: false,
      labelMode: "selected",
      gingivaVisible: false,
      segmentationVisible: true,
      wireframe: false,
      movementVisible: false,
      targetVisible: false,
      treatmentAvailable: false,
      validationAvailable: false,
      canTransform: false,
    });
    render(
      <ContextualWorkspaceToolbar
        tools={tools}
        unavailable={unavailable}
        selectionCount={0}
        onTool={() => undefined}
      />,
    );
    expect(screen.getByTestId("tool-fit-case")).toHaveAttribute("title", expect.stringMatching(/Home/));
    expect(screen.queryByRole("button", { name: "Measure" })).not.toBeInTheDocument();
    expect(screen.getByTestId("toolbar-unavailable")).toHaveTextContent(/Measure/);
  });

  it("adapts the inspector for a blocked case and a selected tooth_ref", () => {
    const segmentation = buildSegmentationReviewModel({
      diagnostic: diagnostic({
        state: "blocked_by_environment",
        runtime_blocker: "pointops missing",
      }),
      teeth: [],
    });
    const blocked = buildInspectorModel({
      minimized: false,
      patientReference: "P-1",
      caseId: "case-1",
      segmentation,
      selected: null,
      selectionCount: 0,
      confidence: null,
      treatmentAvailable: false,
    });
    expect(blocked.mode).toBe("blocked");
    expect(blocked.rows.find((row) => row.label === "Blocker")?.value).toBe("pointops missing");
    const tooth = toothReviewLabel({
      instanceId: 4,
      toothRef: "upper:instance:4",
      arch: "upper",
      fdiNumber: 14,
      fixture: true,
    });
    const selected = buildInspectorModel({
      minimized: false,
      patientReference: "P-1",
      caseId: "case-1",
      segmentation: buildSegmentationReviewModel({
        diagnostic: diagnostic({ provenance: "fixture", fixture: true, state: "identification_incomplete" }),
        teeth: [{ instanceId: 4, toothRef: "upper:instance:4", arch: "upper", fixture: true, fdiNumber: 14 }],
      }),
      selected: tooth,
      selectionCount: 1,
      confidence: null,
      treatmentAvailable: false,
    });
    render(<AdaptiveInspector model={selected} minimized={false} onToggle={() => undefined} />);
    expect(screen.getByTestId("adaptive-inspector")).toHaveAttribute("data-inspector-mode", "tooth");
    expect(screen.getAllByText("upper:instance:4").length).toBeGreaterThan(0);
    expect(screen.getByText("Not resolved")).toBeInTheDocument();
    expect(screen.getByTestId("inspector-advanced")).toBeInTheDocument();
  });

  it("maps keyboard shortcuts and ignores text entry and clinical delete", () => {
    expect(matchWorkspaceShortcut({ key: "Escape", metaKey: false, ctrlKey: false, shiftKey: false, altKey: false })).toBe("clear");
    expect(matchWorkspaceShortcut({ key: "f", metaKey: false, ctrlKey: false, shiftKey: false, altKey: false })).toBe("fit-selection");
    expect(matchWorkspaceShortcut({ key: "Home", metaKey: false, ctrlKey: false, shiftKey: false, altKey: false })).toBe("fit-case");
    expect(matchWorkspaceShortcut({ key: "1", metaKey: false, ctrlKey: false, shiftKey: false, altKey: false })).toBe("arch-upper");
    expect(matchWorkspaceShortcut({ key: "2", metaKey: false, ctrlKey: false, shiftKey: false, altKey: false })).toBe("arch-lower");
    expect(matchWorkspaceShortcut({ key: "0", metaKey: false, ctrlKey: false, shiftKey: false, altKey: false })).toBe("arch-both");
    expect(matchWorkspaceShortcut({ key: "z", metaKey: false, ctrlKey: true, shiftKey: false, altKey: false })).toBe("undo");
    expect(matchWorkspaceShortcut({ key: "Z", metaKey: true, ctrlKey: false, shiftKey: true, altKey: false })).toBe("redo");
    expect(shortcutChangesClinicalState("undo")).toBe(true);
    expect(shortcutChangesClinicalState("fit-case")).toBe(false);
    expect(shortcutChangesClinicalState("clear")).toBe(false);
    expect(deleteShortcutEffect().apply).toBe(false);
    const input = document.createElement("input");
    expect(isTextEntryTarget(input)).toBe(true);
    expect(isTextEntryTarget(document.createElement("div"))).toBe(false);
  });

  it("keeps one primary status surface and a dominant viewport at both acceptance sizes", () => {
    expect(singleStatusSurface(["primary"])).toBe(true);
    expect(singleStatusSurface(["primary", "primary"])).toBe(false);
    for (const size of [
      [1366, 768],
      [1600, 1000],
    ] as const) {
      const budget = layoutBudget(size[0], size[1]);
      expect(budget.viewportDominant).toBe(true);
      expect(budget.pageScroll).toBe(false);
      expect(budget.viewport).toBeGreaterThan(budget.rail);
      expect(budget.viewport).toBeGreaterThan(budget.inspector);
    }
  });

  it("explains workflow dependencies without inventing a completed segmentation", () => {
    expect(
      workflowBlockReason("analysis", {
        hasCase: true,
        bothArchesValid: false,
        hasSegmentation: false,
        segmentationKind: "not_run",
        hasTreatment: false,
      }),
    ).toMatch(/upper and lower/i);
    expect(
      workflowBlockReason("treatment-setup", {
        hasCase: true,
        bothArchesValid: true,
        hasSegmentation: false,
        segmentationKind: "blocked_by_environment",
        hasTreatment: false,
      }),
    ).toMatch(/blocked by environment/i);
    expect(
      headerNextAction({
        workspace: "case-intake",
        hasCase: true,
        bothArchesValid: true,
        hasSegmentation: false,
        hasTreatment: false,
        isBusy: false,
      }),
    ).toBeNull();
    expect(
      headerNextAction({
        workspace: "analysis",
        hasCase: true,
        bothArchesValid: true,
        hasSegmentation: false,
        hasTreatment: false,
        isBusy: false,
      })?.label,
    ).toBe("Create Treatment Plan");
  });

  it("uses elapsed time and refuses an invented ETA", () => {
    const feedback = buildFeedbackModel({
      stageStatus: "PROCESSING",
      userMessage: "Evaluating collisions and proximity",
      elapsedSeconds: 75,
      segmentation: null,
    });
    expect(feedback.state).toBe("processing");
    expect(feedback.elapsedLabel).toBe("Elapsed 01:15");
    expect(feedback.remainingEstimate).toBeNull();
    expect(feedback.remainingNote).toMatch(/No reliable/);
  });

  it("never places synthetic gingiva into a clinical review payload", () => {
    const mesh = resolveGingivaPresentation(engineeringFixtureBundle.stages[0].teeth, null);
    expect(mesh.length).toBeGreaterThan(0);
    expect(mesh.every((item) => item.presentationOnly && item.source === "synthetic")).toBe(true);
    const review = buildSegmentationReviewModel({ diagnostic: null, teeth: [] });
    expect(clinicalPayloadOmitsSyntheticGingiva(review)).toBe(true);
    expect(JSON.stringify(review)).not.toMatch(/synthetic gingiva vertices/i);
  });
});

describe("Wave 3 review strip", () => {
  it("shows blocked provenance and no fabricated FDI", () => {
    const model = buildSegmentationReviewModel({
      diagnostic: diagnostic({
        state: "blocked_by_environment",
        runtime_blocker: "torch missing",
      }),
      teeth: [],
      patientReference: "case-a",
    });
    render(<SegmentationReviewStrip model={model} patientReference="case-a" />);
    expect(screen.getByTestId("analysis-segmentation-state")).toHaveTextContent("Blocked by environment");
    expect(screen.getByTestId("analysis-tooth-count")).toHaveTextContent("Not available");
    expect(screen.getByTestId("segmentation-provenance")).toHaveTextContent("Blocked by environment");
    expect(screen.getByTestId("segmentation-review-strip").textContent).not.toMatch(/FDI \d+/);
  });
});
