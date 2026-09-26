import { describe, expect, it } from "vitest";
import {
  buildArchStatuses,
  buildCaseIntakeReadiness,
  formatCaseStatus,
  formatIntakeProcessingState,
  formatIntakeUploadState,
  formatPreparationReadiness,
  preparationNextStep,
} from "./caseIntake";
import type { ProcessingStatus } from "./api/client";

describe("Case Intake presentation helpers", () => {
  it("labels Upper Arch and Lower Arch statuses without inventing readiness", () => {
    const arches = buildArchStatuses({
      upper: { state: "valid", filename: "u.stl", size: 10 },
      lower: { state: "empty", filename: "", size: 0 },
    });
    expect(arches.map((arch) => arch.label)).toEqual(["Upper Arch", "Lower Arch"]);
    expect(formatIntakeUploadState("valid")).toBe("Valid");
    expect(formatIntakeUploadState("empty")).toBe("Not imported");
    expect(formatPreparationReadiness(null)).toBe("NOT_PREPARED");
    expect(preparationNextStep("READY_WITH_WARNINGS")).toMatch(/Not clinically segmented/);
    expect(preparationNextStep("READY_FOR_SEGMENTATION")).toMatch(/Not clinically segmented/);
  });

  it("reports data completeness from real arch and case state", () => {
    expect(
      buildCaseIntakeReadiness({
        hasCase: false,
        upperState: "empty",
        lowerState: "empty",
      }).completenessLabel,
    ).toBe("Case identity required");

    expect(
      buildCaseIntakeReadiness({
        hasCase: true,
        upperState: "valid",
        lowerState: "empty",
      }),
    ).toMatchObject({
      bothArchesReady: false,
      missing: ["Lower Arch"],
      completenessLabel: "Waiting for Lower Arch",
    });

    expect(
      buildCaseIntakeReadiness({
        hasCase: true,
        upperState: "valid",
        lowerState: "valid",
      }),
    ).toMatchObject({
      bothArchesReady: true,
      missing: [],
      completenessLabel: "Both arches ready",
    });
  });

  it("surfaces processing state from backend status only", () => {
    expect(formatIntakeProcessingState(null)).toEqual({ label: "Idle", detail: null });
    const status: ProcessingStatus = {
      job_id: "j",
      case_id: "c",
      overall_progress: 55,
      current_stage: "SEGMENTING_LOWER",
      stage_status: "PROCESSING",
      stage_progress: null,
      completed_stages: [],
      pending_stages: [],
      error_state: false,
      error_code: null,
      user_message: "Segmenting lower arch",
      started_at: "2026-09-25T00:00:00Z",
      updated_at: "2026-09-25T00:00:00Z",
      completed_at: null,
    };
    expect(formatIntakeProcessingState(status)).toEqual({
      label: "Processing",
      detail: "Segmenting lower arch",
    });
    expect(formatCaseStatus("mesh_validated")).toBe("mesh validated");
  });
});
