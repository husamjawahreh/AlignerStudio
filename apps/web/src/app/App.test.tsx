import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { engineeringFixtureBundle } from "../review/fixtureData";
import { App } from "./App";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return { ...actual, api: { ...actual.api, createEngineeringDemo: vi.fn() } };
});

vi.mock("../viewer/StageViewer", () => ({
  StageViewer: () => <div aria-label="Stage viewer" />,
}));

afterEach(() => vi.clearAllMocks());

describe("App engineering demo", () => {
  it("loads the API fixture demo with visible non-clinical labeling", async () => {
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
    render(<App />);
    await act(async () => {
      screen.getByRole("button", { name: "Load engineering demo" }).click();
    });
    await waitFor(() => expect(screen.getByText("engineering-fixture-demo")).toBeInTheDocument());
    expect(screen.getAllByText(/FIXTURE · not clinically valid/).length).toBeGreaterThan(0);
    expect(screen.queryByText("Real staged review data unavailable")).not.toBeInTheDocument();
    expect(screen.getByText("API engineering fixture")).toBeInTheDocument();
  });

  it("shows a concise API error when the engineering demo cannot load", async () => {
    vi.mocked(api.createEngineeringDemo).mockRejectedValue(new Error("API unavailable"));
    render(<App />);
    await act(async () => {
      screen.getByRole("button", { name: "Load engineering demo" }).click();
    });
    await waitFor(() => expect(screen.getByText("API unavailable")).toBeInTheDocument());
  });

  it("clears fixture review data when creating a real case after the engineering demo", async () => {
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
    vi.spyOn(api, "createCase").mockResolvedValue({
      id: "real-case",
      patient_reference: "P-2",
      status: "created",
      meshes: [],
      created_at: "2026-09-20T00:00:00Z",
    });
    render(<App />);
    await act(async () => {
      screen.getByRole("button", { name: "Load engineering demo" }).click();
    });
    await waitFor(() => expect(screen.getByLabelText("Stage viewer")).toBeInTheDocument());

    await act(async () => {
      screen.getByRole("button", { name: "Create case" }).click();
    });
    await waitFor(() => expect(screen.getByText("Treatment plan unavailable")).toBeInTheDocument());
    expect(screen.queryByLabelText("Stage viewer")).not.toBeInTheDocument();
    expect(screen.queryByText("IPR review")).not.toBeInTheDocument();
    expect(screen.queryByText("Attachments")).not.toBeInTheDocument();
    expect(screen.queryByText(/FIXTURE · not clinically valid/)).not.toBeInTheDocument();
  });

  it("requires valid upper and lower STL uploads before generation is enabled", async () => {
    const createdCase = {
      id: "real-case",
      patient_reference: "P-1",
      status: "created" as const,
      meshes: [],
      created_at: "2026-09-20T00:00:00Z",
    };
    const upperCase = {
      ...createdCase,
      status: "mesh_validated" as const,
      meshes: [
        {
          arch: "upper" as const,
          file_path: "/tmp/upper.stl",
          original_filename: "upper.stl",
          uploaded_at: "2026-09-20T00:00:00Z",
        },
      ],
    };
    const bothCase = {
      ...upperCase,
      meshes: [
        ...upperCase.meshes,
        {
          arch: "lower" as const,
          file_path: "/tmp/lower.stl",
          original_filename: "lower.stl",
          uploaded_at: "2026-09-20T00:00:00Z",
        },
      ],
    };
    vi.spyOn(api, "createCase").mockResolvedValue(createdCase);
    vi.spyOn(api, "uploadMesh").mockImplementation(async (_caseId, arch) =>
      arch === "upper" ? upperCase : bothCase,
    );
    vi.spyOn(api, "validateMesh").mockResolvedValue({
      is_valid: true,
      triangle_count: 1000,
      is_watertight: true,
      errors: [],
    });
    vi.spyOn(api, "processPipeline").mockResolvedValue({
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
      failures: ["No fixture fallback is used."],
      arch_analysis_available: false,
      notes: [],
    });
    render(<App />);
    expect(screen.getByLabelText("Upper arch STL")).toBeInTheDocument();
    expect(screen.getByLabelText("Lower arch STL")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate plan" })).toBeDisabled();

    await act(async () => {
      screen.getByRole("button", { name: "Create case" }).click();
    });
    const upper = new File(["upper"], "upper.stl", { type: "model/stl" });
    fireEvent.change(screen.getByLabelText("Upper arch STL"), { target: { files: [upper] } });
    await waitFor(() => expect(screen.getByText("upper.stl")).toBeInTheDocument());
    expect(screen.getByText("0.0 KB · valid")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate plan" })).toBeDisabled();

    const lower = new File(["lower"], "lower.stl", { type: "model/stl" });
    fireEvent.change(screen.getByLabelText("Lower arch STL"), { target: { files: [lower] } });
    await waitFor(() => expect(screen.getByText("lower.stl")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Generate plan" })).toBeEnabled();

    await act(async () => {
      screen.getByRole("button", { name: "Generate plan" }).click();
    });
    await waitFor(() =>
      expect(screen.getByText("Segmentation model unavailable")).toBeInTheDocument(),
    );
    expect(screen.queryByLabelText("Stage viewer")).not.toBeInTheDocument();
    expect(screen.queryByText(/FIXTURE · not clinically valid/)).not.toBeInTheDocument();
  });
});
