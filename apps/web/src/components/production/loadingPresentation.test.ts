import { describe, expect, it } from "vitest";
import type { ProcessingStatus } from "../../api/client";
import {
  formatStageId,
  loadingFromLocalActivity,
  loadingFromProcessingStatus,
  resolveLoadingPresentation,
} from "./loadingPresentation";

function status(partial: Partial<ProcessingStatus>): ProcessingStatus {
  return {
    job_id: "job-1",
    case_id: "case-1",
    overall_progress: 0,
    current_stage: "PREPARING",
    stage_status: "PROCESSING",
    stage_progress: null,
    completed_stages: [],
    pending_stages: ["PREPARING", "VALIDATING_SCANS"],
    error_state: false,
    error_code: null,
    user_message: "Analyzing case",
    started_at: "2026-09-25T00:00:00Z",
    updated_at: "2026-09-25T00:00:00Z",
    completed_at: null,
    elapsed_seconds: 12,
    ...partial,
  };
}

describe("loadingPresentation", () => {
  it("formats backend stage ids without inventing new milestones", () => {
    expect(formatStageId("SEGMENTING_UPPER")).toBe("Segmenting Upper");
    expect(formatStageId("BUILDING_PLAN")).toBe("Building Plan");
  });

  it("uses backend overall_progress and reported stages only", () => {
    const presentation = loadingFromProcessingStatus(
      status({
        overall_progress: 55,
        current_stage: "SEGMENTING_LOWER",
        user_message: "Segmenting lower arch",
        completed_stages: ["VALIDATING_SCANS", "SEGMENTING_UPPER"],
        pending_stages: ["BUILDING_PLAN", "FINALIZING"],
      }),
    );
    expect(presentation.mode).toBe("determinate");
    expect(presentation.progressPercent).toBe(55);
    expect(presentation.title).toBe("Segmenting lower arch");
    expect(presentation.source).toBe("backend-processing");
    expect(presentation.stages.map((stage) => stage.id)).toEqual([
      "VALIDATING_SCANS",
      "SEGMENTING_UPPER",
      "SEGMENTING_LOWER",
      "BUILDING_PLAN",
      "FINALIZING",
    ]);
    expect(presentation.stages.find((stage) => stage.id === "SEGMENTING_LOWER")?.state).toBe("current");
    expect(presentation.stages.find((stage) => stage.id === "VALIDATING_SCANS")?.state).toBe("completed");
  });

  it("never invents a percentage for local activity", () => {
    const presentation = loadingFromLocalActivity("Uploading upper scan");
    expect(presentation.mode).toBe("indeterminate");
    expect(presentation.progressPercent).toBeNull();
    expect(presentation.stages).toEqual([]);
    expect(presentation.source).toBe("local-activity");
  });

  it("prefers live backend processing over local busy labels", () => {
    const presentation = resolveLoadingPresentation({
      processingStatus: status({ overall_progress: 70, user_message: "Preparing treatment setup" }),
      isBusy: true,
      busyActivity: "Starting analysis",
      recalculationState: "idle",
    });
    expect(presentation?.title).toBe("Preparing treatment setup");
    expect(presentation?.progressPercent).toBe(70);
    expect(presentation?.source).toBe("backend-processing");
  });

  it("keeps completed backend status visible while treatment payload is still loading", () => {
    const presentation = resolveLoadingPresentation({
      processingStatus: status({
        stage_status: "COMPLETED",
        overall_progress: 100,
        user_message: "Case ready",
        current_stage: "FINALIZING",
        completed_stages: ["FINALIZING"],
        pending_stages: [],
      }),
      isBusy: true,
      busyActivity: null,
      recalculationState: "idle",
    });
    expect(presentation?.progressPercent).toBe(100);
    expect(presentation?.title).toBe("Case ready");
  });

  it("falls back to recalculation activity without a fake percent", () => {
    const presentation = resolveLoadingPresentation({
      processingStatus: null,
      isBusy: false,
      busyActivity: null,
      recalculationState: "recalculating",
    });
    expect(presentation?.mode).toBe("indeterminate");
    expect(presentation?.progressPercent).toBeNull();
    expect(presentation?.title).toBe("Recalculating treatment plan");
  });
});
