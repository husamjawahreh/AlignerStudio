import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CaseLoadingOverlay } from "./ProductionPrimitives";
import { loadingFromLocalActivity, loadingFromProcessingStatus } from "./loadingPresentation";
import type { ProcessingStatus } from "../../api/client";

const baseStatus: ProcessingStatus = {
  job_id: "job-1",
  case_id: "case-1",
  overall_progress: 55,
  current_stage: "SEGMENTING_LOWER",
  stage_status: "PROCESSING",
  stage_progress: null,
  completed_stages: ["VALIDATING_SCANS", "SEGMENTING_UPPER"],
  pending_stages: ["BUILDING_PLAN"],
  error_state: false,
  error_code: null,
  user_message: "Segmenting lower arch",
  started_at: "2026-09-25T00:00:00Z",
  updated_at: "2026-09-25T00:00:10Z",
  completed_at: null,
  elapsed_seconds: 42,
};

describe("CaseLoadingOverlay", () => {
  it("renders branded determinate progress from backend presentation", () => {
    render(<CaseLoadingOverlay presentation={loadingFromProcessingStatus(baseStatus)} />);
    const overlay = screen.getByTestId("case-loading-overlay");
    expect(overlay).toHaveAttribute("data-loading-source", "backend-processing");
    expect(overlay).toHaveAttribute("data-loading-mode", "determinate");
    expect(screen.getByText("Aligner Studio")).toBeInTheDocument();
    expect(screen.getByText("Segmenting lower arch")).toBeInTheDocument();
    expect(screen.getByText("55% from server")).toBeInTheDocument();
    expect(screen.getByText("Elapsed 00:42")).toBeInTheDocument();
    expect(screen.getByText("SEGMENTING_LOWER")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "55");
    expect(screen.getByText("Validating Scans")).toBeInTheDocument();
  });

  it("renders indeterminate overlay without inventing a percentage", () => {
    render(<CaseLoadingOverlay presentation={loadingFromLocalActivity("Uploading upper scan")} />);
    const overlay = screen.getByTestId("case-loading-overlay");
    expect(overlay).toHaveAttribute("data-loading-mode", "indeterminate");
    expect(screen.getByText("Uploading upper scan")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });
});
