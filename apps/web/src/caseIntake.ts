import type { ProcessingStatus } from "./api/client";

export type IntakeArch = "upper" | "lower";
export type IntakeUploadState = "empty" | "uploading" | "valid" | "invalid" | "error";

export interface IntakeArchStatus {
  arch: IntakeArch;
  label: "Upper Arch" | "Lower Arch";
  state: IntakeUploadState;
  filename: string;
  size: number;
}

export interface CaseIntakeReadiness {
  hasCase: boolean;
  upperReady: boolean;
  lowerReady: boolean;
  bothArchesReady: boolean;
  missing: string[];
  completenessLabel: string;
}

/** Human label for an arch upload state — presentation only. */
export function formatIntakeUploadState(state: IntakeUploadState): string {
  switch (state) {
    case "empty":
      return "Not imported";
    case "uploading":
      return "Uploading";
    case "valid":
      return "Valid";
    case "invalid":
      return "Invalid";
    case "error":
      return "Error";
    default:
      return state;
  }
}

export function buildArchStatuses(input: {
  upper: { state: IntakeUploadState; filename: string; size: number };
  lower: { state: IntakeUploadState; filename: string; size: number };
}): IntakeArchStatus[] {
  return [
    {
      arch: "upper",
      label: "Upper Arch",
      state: input.upper.state,
      filename: input.upper.filename,
      size: input.upper.size,
    },
    {
      arch: "lower",
      label: "Lower Arch",
      state: input.lower.state,
      filename: input.lower.filename,
      size: input.lower.size,
    },
  ];
}

export function buildCaseIntakeReadiness(input: {
  hasCase: boolean;
  upperState: IntakeUploadState;
  lowerState: IntakeUploadState;
}): CaseIntakeReadiness {
  const upperReady = input.upperState === "valid";
  const lowerReady = input.lowerState === "valid";
  const missing: string[] = [];
  if (!input.hasCase) missing.push("Case Information");
  if (!upperReady) missing.push("Upper Arch");
  if (!lowerReady) missing.push("Lower Arch");
  const bothArchesReady = upperReady && lowerReady;
  return {
    hasCase: input.hasCase,
    upperReady,
    lowerReady,
    bothArchesReady,
    missing,
    completenessLabel: !input.hasCase
      ? "Case identity required"
      : bothArchesReady
        ? "Both arches ready"
        : missing.length === 1
          ? `Waiting for ${missing[0]}`
          : `Waiting for ${missing.join(" and ")}`,
  };
}

/** Processing state from live backend status — never invents progress. */
export function formatIntakeProcessingState(
  status: ProcessingStatus | null | undefined,
): { label: string; detail: string | null } {
  if (!status) return { label: "Idle", detail: null };
  if (status.stage_status === "PROCESSING") {
    return {
      label: "Processing",
      detail: status.user_message || status.current_stage || null,
    };
  }
  if (status.stage_status === "COMPLETED") {
    return { label: "Completed", detail: status.user_message || "Case ready" };
  }
  if (status.stage_status === "FAILED") {
    return { label: "Failed", detail: status.user_message || "Processing failed" };
  }
  if (status.stage_status === "CANCELLED") {
    return { label: "Cancelled", detail: status.user_message || null };
  }
  if (status.stage_status === "STALE") {
    return {
      label: "Stopped responding",
      detail: status.user_message || "Start analysis again.",
    };
  }
  return { label: status.stage_status, detail: status.user_message || null };
}

export function formatCaseStatus(status: string | null | undefined): string {
  if (!status) return "No case";
  return status.replaceAll("_", " ");
}
