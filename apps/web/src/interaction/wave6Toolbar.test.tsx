import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ContextualWorkspaceToolbar, SmartWidgets } from "../components/workspace/ClinicalChrome";
import { matchWorkspaceShortcut } from "./model";
import {
  commandIdForShortcut,
  resolveToolbar,
  resolveToolbarContext,
  viewportCommandMutatesClinicalState,
  viewportOccupancy,
  type ToolbarMachineInput,
} from "./toolbar";
import { resolveWidgets, widgetsDuplicate, type WidgetInput } from "./widgets";

function machine(patch: Partial<ToolbarMachineInput> = {}): ToolbarMachineInput {
  return {
    workspace: "analysis",
    hasCase: true,
    sceneAvailable: true,
    segmentationKind: "real_model_inference",
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

function widgets(patch: Partial<WidgetInput> = {}): WidgetInput {
  return {
    selectionCount: 0,
    selectionLabel: null,
    selectionArch: null,
    groupArches: null,
    groupIdentity: null,
    identityUnresolved: false,
    fixture: false,
    provenanceLabel: null,
    provenanceStripVisible: false,
    processing: false,
    processingOwnedByStatus: false,
    phase: null,
    elapsedLabel: null,
    serverProgress: null,
    canCancel: false,
    targetGeometryExists: false,
    showTarget: false,
    showCurrent: true,
    stagingCount: 0,
    stagingIndex: null,
    stagingStale: false,
    stagingTimelineVisible: false,
    validationAvailable: false,
    validationFindingCount: null,
    validationPanelVisible: false,
    dependencyText: null,
    orientationVisible: false,
    ...patch,
  };
}

function ids(items: { id: string }[]): string[] {
  return items.map((item) => item.id);
}

describe("Wave 6 toolbar state machine", () => {
  it("resolves the required contexts", () => {
    expect(resolveToolbarContext(machine({ hasCase: false, workspace: "case-intake", sceneAvailable: false }))).toBe("idle");
    expect(resolveToolbarContext(machine({ workspace: "case-intake", sceneAvailable: false }))).toBe("case");
    expect(resolveToolbarContext(machine({ selectionCount: 1 }))).toBe("one-tooth");
    expect(resolveToolbarContext(machine({ selectionCount: 2 }))).toBe("multi-tooth");
    expect(resolveToolbarContext(machine())).toBe("segmentation-review");
    expect(resolveToolbarContext(machine({ workspace: "treatment-setup" }))).toBe("treatment-setup");
    expect(resolveToolbarContext(machine({ workspace: "staging" }))).toBe("staging");
    expect(resolveToolbarContext(machine({ workspace: "refinement" }))).toBe("refinement");
    expect(resolveToolbarContext(machine({ workspace: "validation" }))).toBe("validation");
    expect(resolveToolbarContext(machine({ workspace: "production" }))).toBe("production");
    expect(resolveToolbarContext(machine({ stageStatus: "PROCESSING" }))).toBe("processing");
    expect(resolveToolbarContext(machine({ segmentationKind: "blocked_by_environment" }))).toBe("blocked");
    expect(resolveToolbarContext(machine({ segmentationKind: "failed", canRetrySegmentation: true }))).toBe("failed");
    expect(resolveToolbarContext(machine({ workspace: "staging", stagingStale: true, sceneAvailable: false }))).toBe("stale");
    expect(resolveToolbarContext(machine({ segmentationKind: "not_available", sceneAvailable: false }))).toBe("unavailable");
  });

  it("keeps selection context when staging is stale and a tooth is selected", () => {
    expect(
      resolveToolbarContext(machine({ workspace: "staging", stagingStale: true, selectionCount: 1, canRegenerateStaging: true })),
    ).toBe("one-tooth");
    expect(
      resolveToolbarContext(machine({ workspace: "refinement", stagingStale: true, canRegenerateStaging: true })),
    ).toBe("refinement");
  });

  it("orders primary actions by priority and parks utilities in More", () => {
    const toolbar = resolveToolbar(machine());
    const priorities = toolbar.primary.map((item) => item.priority);
    expect(priorities).toEqual([...priorities].sort((a, b) => a - b));
    expect(ids(toolbar.more)).toEqual(expect.arrayContaining(["reset-view", "gingiva", "wireframe"]));
    expect(toolbar.primary.every((item) => item.priority < 6)).toBe(true);
    expect(ids(toolbar.primary)).not.toContain("measure");
    expect(ids(toolbar.primary)).not.toContain("move");
  });

  it("shows fit and camera tools with no selection, and fit selection for one or many teeth", () => {
    const idle = resolveToolbar(machine());
    expect(ids(idle.primary)).toEqual(
      expect.arrayContaining(["fit-case", "fit-arch", "view-occlusal", "view-front", "view-lateral", "arch-upper", "labels"]),
    );
    const selected = resolveToolbar(machine({ selectionCount: 1 }));
    expect(ids(selected.more)).toEqual(expect.arrayContaining(["view-occlusal", "view-front", "view-lateral"]));
    expect(selected.primary.length).toBeLessThanOrEqual(14);
    expect(ids(idle.primary)).not.toContain("fit-selection");
    expect(ids(idle.primary)).not.toContain("isolate");

    const one = resolveToolbar(machine({ selectionCount: 1 }));
    expect(ids(one.primary)).toEqual(expect.arrayContaining(["fit-selection", "isolate"]));
    expect(one.primary.find((item) => item.id === "fit-selection")?.shortcut).toBe("F");

    const many = resolveToolbar(machine({ selectionCount: 3, groupIdentity: "same" }));
    expect(ids(many.primary)).toContain("fit-selection");
    expect(ids(many.primary)).not.toContain("isolate");
    expect(ids(many.withheld)).not.toContain("group-numbering");

    const mixed = resolveToolbar(machine({ selectionCount: 2, groupIdentity: "mixed" }));
    const numbering = mixed.withheld.find((item) => item.id === "group-numbering");
    expect(numbering?.availability).toBe("unavailable");
    expect(ids(mixed.primary)).not.toContain("group-numbering");
  });

  it("keeps workflow actions on the step that can run them", () => {
    const setup = resolveToolbar(
      machine({ workspace: "treatment-setup", targetGeometryExists: true, treatmentAvailable: true }),
    );
    expect(ids(setup.primary)).toEqual(expect.arrayContaining(["target", "movement", "fit-case"]));

    const noTarget = resolveToolbar(machine({ workspace: "treatment-setup" }));
    expect(noTarget.withheld.find((item) => item.id === "target")?.availability).toBe("unavailable");
    expect(ids(noTarget.primary)).not.toContain("target");

    const staging = resolveToolbar(
      machine({
        workspace: "staging",
        stagingStale: true,
        canRegenerateStaging: true,
        sceneAvailable: false,
        stagingCount: 3,
      }),
    );
    expect(staging.context).toBe("stale");
    expect(staging.primary.find((item) => item.id === "regenerate-staging")?.availability).toBe("stale");

    const refinement = resolveToolbar(
      machine({ workspace: "refinement", selectionCount: 1, canUndo: true, canRedo: true, manipulationOwnedByToothToolbar: true }),
    );
    expect(ids(refinement.primary)).toEqual(expect.arrayContaining(["undo", "redo"]));
    expect(refinement.withheld.find((item) => item.id === "move")?.reason).toMatch(/selected-tooth controls/);

    const validation = resolveToolbar(
      machine({ workspace: "validation", validationAvailable: true, validationFindingCount: 2 }),
    );
    const overlay = validation.withheld.find((item) => item.id === "validation-overlay");
    expect(overlay?.availability).toBe("unavailable");
    expect(overlay?.reason).toMatch(/approval/i);
    expect(ids(validation.primary)).not.toContain("validation-overlay");
  });

  it("describes processing, blocked, failed, stale, and unavailable without a fake enabled button", () => {
    const processing = resolveToolbar(
      machine({ stageStatus: "PROCESSING", canCancelProcessing: true, selectionCount: 1 }),
    );
    expect(processing.context).toBe("processing");
    expect(ids(processing.primary)).toEqual(["cancel-processing"]);
    expect(ids(processing.primary)).not.toContain("fit-case");
    expect(processing.primary[0]?.effect).toBe("job");

    const blocked = resolveToolbar(machine({ segmentationKind: "blocked_by_environment", sceneAvailable: false }));
    const retry = blocked.withheld.find((item) => item.id === "retry-segmentation");
    expect(retry?.availability).toBe("blocked");
    expect(retry?.reason).toMatch(/environment blocker, not a model failure/);
    expect(ids(blocked.primary)).not.toContain("retry-segmentation");

    const failed = resolveToolbar(
      machine({ segmentationKind: "failed", canRetrySegmentation: true, sceneAvailable: false }),
    );
    expect(failed.primary.find((item) => item.id === "retry-segmentation")?.availability).toBe("available");

    const unavailable = resolveToolbar(machine({ segmentationKind: "not_available", sceneAvailable: false }));
    expect(unavailable.context).toBe("unavailable");
    expect(unavailable.withheld.find((item) => item.id === "measure")?.availability).toBe("unavailable");
    expect(ids(unavailable.primary)).not.toContain("measure");
  });

  it("does not repeat a suppressed next action", () => {
    const toolbar = resolveToolbar(
      machine({
        segmentationKind: "failed",
        canRetrySegmentation: true,
        sceneAvailable: false,
        suppressedIds: ["retry-segmentation"],
      }),
    );
    expect(ids([...toolbar.primary, ...toolbar.more, ...toolbar.withheld])).not.toContain("retry-segmentation");
  });

  it("gives every action an explicit schema", () => {
    const toolbar = resolveToolbar(machine({ selectionCount: 1 }));
    for (const item of [...toolbar.primary, ...toolbar.more, ...toolbar.withheld]) {
      expect(item.id).toBeTruthy();
      expect(item.label).toBeTruthy();
      expect(item.category).toBeTruthy();
      expect(["available", "unavailable", "blocked", "requires_review", "stale"]).toContain(item.availability);
      expect(item.reason.length).toBeGreaterThan(8);
      expect(item.priority).toBeGreaterThanOrEqual(1);
      expect(item.destructive).toBe(false);
      expect(item.executable).toBe(
        item.availability === "available" || item.availability === "requires_review" || item.availability === "stale",
      );
    }
  });
});

describe("Wave 6 widgets", () => {
  it("shows a compact selection widget and withholds it when nothing is selected", () => {
    expect(resolveWidgets(widgets()).map((item) => item.id)).not.toContain("selection");
    const one = resolveWidgets(
      widgets({
        selectionCount: 1,
        selectionLabel: "upper:instance:0",
        selectionArch: "upper",
        identityUnresolved: true,
      }),
    );
    expect(one[0]?.value).toBe("upper:instance:0");
    expect(one[0]?.detail).toMatch(/upper/);
    expect(one[0]?.detail).toMatch(/Unresolved/);
    expect(one[0]?.value).not.toMatch(/FDI/);

    const group = resolveWidgets(
      widgets({
        selectionCount: 2,
        groupArches: "upper, lower",
        groupIdentity: "mixed",
        identityUnresolved: true,
        fixture: true,
      }),
    );
    expect(group[0]?.value).toBe("2 teeth");
    expect(group[0]?.detail).toMatch(/Identity differs/);
    expect(group[0]?.detail).toMatch(/Fixture \/ test-only/);
  });

  it("hides widgets that would duplicate status, the timeline, the strip, or the validation panel", () => {
    const hidden = resolveWidgets(
      widgets({
        processing: true,
        processingOwnedByStatus: true,
        phase: "SEGMENTING_LOWER",
        stagingCount: 4,
        stagingTimelineVisible: true,
        provenanceLabel: "ToothInstanceNet",
        provenanceStripVisible: true,
        validationAvailable: true,
        validationFindingCount: 3,
        validationPanelVisible: true,
        dependencyText: "Treatment is not stored",
        orientationVisible: true,
      }),
    );
    expect(hidden.map((item) => item.id)).toEqual([]);

    const shown = resolveWidgets(
      widgets({
        processing: true,
        phase: "SEGMENTING_LOWER",
        elapsedLabel: "Elapsed 00:02",
        serverProgress: null,
        canCancel: true,
      }),
    );
    expect(shown[0]?.id).toBe("processing");
    expect(shown[0]?.detail).toMatch(/indeterminate/i);
    expect(shown[0]?.detail).not.toMatch(/remaining/i);
  });

  it("renders current/target, staging, validation, and provenance only with evidence", () => {
    expect(resolveWidgets(widgets()).map((item) => item.id)).not.toContain("current-target");
    const geometry = resolveWidgets(widgets({ targetGeometryExists: true, showTarget: true, showCurrent: true }));
    expect(geometry[0]?.value).toBe("Current and target");
    expect(geometry[0]?.detail).toMatch(/Not an approval/);

    expect(resolveWidgets(widgets()).map((item) => item.id)).not.toContain("staging");
    const stage = resolveWidgets(widgets({ stagingCount: 12, stagingIndex: 2, stagingStale: true }));
    expect(stage[0]?.value).toBe("3 / 12");
    expect(stage[0]?.detail).toMatch(/Stale/);
    expect(stage[0]?.detail).not.toMatch(/optimal/i);

    const findings = resolveWidgets(widgets({ validationAvailable: true, validationFindingCount: 4 }));
    expect(findings[0]?.value).toBe("4 findings");
    expect(findings[0]?.detail).toMatch(/Not a score and not an approval/);
    expect(findings[0]?.value).not.toMatch(/safe|%/i);

    const provenance = resolveWidgets(widgets({ provenanceLabel: "ToothInstanceNet", fixture: false }));
    expect(provenance[0]?.detail).toMatch(/Advanced details/);
    const fixture = resolveWidgets(widgets({ fixture: true, provenanceLabel: "should-not-win" }));
    expect(fixture[0]?.value).toBe("Fixture / test-only");
    expect(fixture[0]?.detail).toMatch(/Not patient inference/);
  });

  it("caps widgets at two and rejects duplicate copy", () => {
    const models = resolveWidgets(
      widgets({
        selectionCount: 1,
        selectionLabel: "upper:instance:0",
        selectionArch: "upper",
        targetGeometryExists: true,
        showTarget: false,
        validationAvailable: true,
        validationFindingCount: 2,
        provenanceLabel: "backend",
        stagingCount: 3,
        stagingIndex: 0,
      }),
    );
    expect(models).toHaveLength(2);
    expect(models.map((item) => item.id)).toEqual(["selection", "current-target"]);
    expect(widgetsDuplicate(models)).toBe(false);
    expect(
      widgetsDuplicate([
        { id: "selection", testId: "selection-widget", eyebrow: "Selected tooth", value: "same", detail: "same" },
        { id: "provenance", testId: "provenance-widget", eyebrow: "Provenance", value: "same", detail: "same" },
      ]),
    ).toBe(true);
  });
});

describe("Wave 6 commands, availability, and occupancy", () => {
  it("maps keyboard shortcuts onto the same command ids as the toolbar", () => {
    const keys = [
      ["Escape", "clear", "clear-selection"],
      ["f", "fit-selection", "fit-selection"],
      ["Home", "fit-case", "fit-case"],
      ["1", "arch-upper", "arch-upper"],
      ["2", "arch-lower", "arch-lower"],
      ["0", "arch-both", "arch-both"],
    ] as const;
    for (const [key, shortcut, command] of keys) {
      const matched = matchWorkspaceShortcut({ key, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false });
      expect(matched).toBe(shortcut);
      expect(commandIdForShortcut(matched!)).toBe(command);
    }
    expect(
      commandIdForShortcut(
        matchWorkspaceShortcut({ key: "z", metaKey: true, ctrlKey: false, shiftKey: false, altKey: false })!,
      ),
    ).toBe("undo");
    expect(
      commandIdForShortcut(
        matchWorkspaceShortcut({ key: "z", metaKey: false, ctrlKey: true, shiftKey: true, altKey: false })!,
      ),
    ).toBe("redo");
    expect(commandIdForShortcut("delete")).toBeNull();

    const seen: string[] = [];
    render(
      <ContextualWorkspaceToolbar
        context="one-tooth"
        tools={[
          {
            id: "fit-case",
            label: "Fit case",
            available: true,
            reason: "Frame the full case. Shortcut Home.",
            shortcut: "Home",
            availability: "available",
          },
        ]}
        unavailable={[{ id: "measure", label: "Measure", reason: "No measurement tool is active.", availability: "unavailable" }]}
        onTool={(id) => seen.push(id)}
      />,
    );
    fireEvent.click(screen.getByTestId("tool-fit-case"));
    expect(seen).toEqual(["fit-case"]);
    expect(commandIdForShortcut("fit-case")).toBe("fit-case");
    expect(screen.queryByTestId("tool-measure")).toBeNull();
    expect(screen.getByTestId("toolbar-unavailable")).toHaveTextContent("why".replace("why", "No measurement tool"));
  });

  it("keeps viewport commands off the clinical edit stack", () => {
    for (const id of ["fit-case", "fit-selection", "arch-upper", "labels", "target", "isolate"]) {
      expect(viewportCommandMutatesClinicalState(id)).toBe(false);
    }
    expect(viewportCommandMutatesClinicalState("undo")).toBe(true);
    expect(viewportCommandMutatesClinicalState("redo")).toBe(true);
    const fit = resolveToolbar(machine()).primary.find((item) => item.id === "fit-case");
    expect(fit?.effect).toBe("view");
    const undo = resolveToolbar(
      machine({ workspace: "refinement", canUndo: true }),
    ).primary.find((item) => item.id === "undo");
    expect(undo?.effect).toBe("durable-edit");
  });

  it("keeps the viewport dominant at the desktop sizes", () => {
    for (const size of [
      [1366, 768],
      [1600, 1000],
      [1280, 800],
    ] as const) {
      const budget = viewportOccupancy({ width: size[0], height: size[1], primaryToolCount: 12, widgetCount: 2 });
      expect(budget.viewportDominant).toBe(true);
      expect(budget.widgetCountWithinCap).toBe(true);
      expect(budget.primaryToolsWithinCap).toBe(true);
    }
    expect(viewportOccupancy({ width: 1366, height: 768, primaryToolCount: 12, widgetCount: 3 }).widgetCountWithinCap).toBe(false);
  });
});

describe("Wave 6 widget rendering", () => {
  it("renders at most the resolved widgets and does not add a second status line", () => {
    render(
      <SmartWidgets
        models={resolveWidgets(
          widgets({
            selectionCount: 1,
            selectionLabel: "upper:instance:0",
            selectionArch: "upper",
            fixture: true,
            identityUnresolved: true,
          }),
        )}
      />,
    );
    expect(screen.getByTestId("selection-widget")).toHaveTextContent("upper:instance:0");
    expect(screen.getByTestId("selection-widget")).toHaveTextContent("Fixture / test-only");
    expect(screen.queryByTestId("processing-widget")).toBeNull();
    expect(screen.queryByText(/safe/i)).toBeNull();
  });
});
