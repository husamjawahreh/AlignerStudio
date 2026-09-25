import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { ACTIVE_CASE_STORAGE_KEY } from "../caseWorkspacePersistence";
import { engineeringFixtureBundle } from "../review/fixtureData";
import { reviewToothKey } from "../viewer/toothKey";
import { App } from "./App";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      createEngineeringDemo: vi.fn(),
      getCase: vi.fn(),
      getTreatment: vi.fn(),
      getProcessingStatus: vi.fn(),
      applyTreatmentEdit: vi.fn(),
    },
  };
});

vi.mock("../viewer/StageViewer", () => ({
  StageViewer: ({
    stage,
    onSelectTooth,
  }: {
    stage?: { teeth: Parameters<typeof reviewToothKey>[0][] };
    onSelectTooth: (toothRef: string) => void;
  }) => (
    <div aria-label="Stage viewer">
      {(stage?.teeth ?? []).map((tooth) => {
        const key = reviewToothKey(tooth);
        return (
          <button key={key} type="button" aria-label={`Select ${key}`} onClick={() => onSelectTooth(key)}>
            {key}
          </button>
        );
      })}
    </div>
  ),
}));

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

describe("P8 browser refresh rehydrate", () => {
  it("restores remembered case metadata and treatment from the API on mount", async () => {
    sessionStorage.setItem(ACTIVE_CASE_STORAGE_KEY, "restored-case");
    vi.mocked(api.getCase).mockResolvedValue({
      id: "restored-case",
      patient_reference: "P-RESTORE",
      status: "plan_generated",
      meshes: [
        {
          arch: "upper",
          file_path: "/tmp/upper.stl",
          original_filename: "upper.stl",
          uploaded_at: "2026-09-20T00:00:00Z",
        },
        {
          arch: "lower",
          file_path: "/tmp/lower.stl",
          original_filename: "lower.stl",
          uploaded_at: "2026-09-20T00:00:00Z",
        },
      ],
      created_at: "2026-09-20T00:00:00Z",
    });
    vi.mocked(api.getProcessingStatus).mockRejectedValue(new Error("No processing job"));
    vi.mocked(api.getTreatment).mockResolvedValue({
      ...engineeringFixtureBundle,
      realDataAvailable: true,
    });

    render(<App />);

    await waitFor(() => expect(api.getCase).toHaveBeenCalledWith("restored-case"));
    await waitFor(() => expect(screen.getByText("P-RESTORE")).toBeInTheDocument());
    await waitFor(() => expect(api.getTreatment).toHaveBeenCalledWith("restored-case"));
    await waitFor(() => expect(screen.getByLabelText("Stage viewer")).toBeInTheDocument());
  });
});

describe("P8 undo/redo on engineering fixture path", () => {
  it("enables Undo after Apply and restores prior draft via Undo then Redo", async () => {
    const tooth = engineeringFixtureBundle.stages[0].teeth[0];
    const key = reviewToothKey(tooth);

    vi.mocked(api.createEngineeringDemo).mockResolvedValue({
      case: {
        id: "fixture-case",
        patient_reference: "engineering-fixture-demo",
        status: "plan_generated",
        meshes: [],
        created_at: "2026-09-20T00:00:00Z",
      },
      review_bundle: { ...engineeringFixtureBundle, realDataAvailable: true },
    });
    vi.mocked(api.applyTreatmentEdit).mockImplementation(async (_caseId, _tooth, movement) => ({
      ...engineeringFixtureBundle,
      realDataAvailable: true,
      stages: engineeringFixtureBundle.stages.map((stage, index) =>
        index === 0
          ? {
              ...stage,
              teeth: stage.teeth.map((item) =>
                reviewToothKey(item) === key ? { ...item, movement: { ...item.movement, ...movement } } : item,
              ),
            }
          : stage,
      ),
    }));

    render(<App />);
    await act(async () => {
      screen.getByRole("button", { name: "Load engineering demo" }).click();
    });
    await waitFor(() => expect(screen.getByLabelText("Stage viewer")).toBeInTheDocument());

    await act(async () => {
      screen.getByRole("button", { name: /Refinement/ }).click();
    });

    await act(async () => {
      screen.getByRole("button", { name: `Select ${key}` }).click();
    });

    const translationInput = await screen.findByLabelText("Translation X");
    const before = (translationInput as HTMLInputElement).value;
    await act(async () => {
      fireEvent.change(translationInput, { target: { value: "0.42" } });
    });
    await act(async () => {
      screen.getByRole("button", { name: "Apply" }).click();
    });

    const undo = await screen.findByRole("button", { name: "Undo doctor edit" });
    await waitFor(() => expect(undo).not.toBeDisabled());
    await act(async () => {
      undo.click();
    });
    await waitFor(() => {
      expect((screen.getByLabelText("Translation X") as HTMLInputElement).value).toBe(before);
    });

    const redo = screen.getByRole("button", { name: "Redo doctor edit" });
    await act(async () => {
      redo.click();
    });
    await waitFor(() => {
      expect(Number((screen.getByLabelText("Translation X") as HTMLInputElement).value)).toBeCloseTo(
        0.42,
        2,
      );
    });
  });
});
