import type { ProcessingStatus } from "../../api/client";
import { NO_RELIABLE_REMAINING_TIME, presentRemainingTime } from "../../performance/remainingTime";

export type LoadingMode = "determinate" | "indeterminate";

export interface LoadingStageChip {
  id: string;
  label: string;
  state: "completed" | "current" | "pending";
}

export interface LoadingPresentation {
  brand: "Aligner Studio";
  title: string;
  detail: string;
  mode: LoadingMode;
  /** Present only when the backend provided a real overall_progress value. */
  progressPercent: number | null;
  elapsedSeconds: number | null;
  /** Evidence-based remaining sentence, or the explicit no-estimate sentence. */
  remainingLabel: string;
  currentStageId: string | null;
  stages: LoadingStageChip[];
  source: "backend-processing" | "local-activity";
}

/** Humanize a backend stage id for display — does not invent new milestones. */
export function formatStageId(stageId: string): string {
  return stageId
    .toLowerCase()
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatElapsed(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return `${minutes.toString().padStart(2, "0")}:${remainder.toString().padStart(2, "0")}`;
}

export function formatElapsedLabel(seconds: number | null | undefined): string | null {
  if (seconds == null || !Number.isFinite(seconds)) return null;
  return `Elapsed ${formatElapsed(seconds)}`;
}

/**
 * Build a loading view from live ProcessingStatus.
 * Progress and stages come only from the payload — never invented.
 */
export function loadingFromProcessingStatus(status: ProcessingStatus): LoadingPresentation {
  const completed = status.completed_stages ?? [];
  const pending = status.pending_stages ?? [];
  const current = status.current_stage;
  const knownIds = Array.from(
    new Set([...completed, ...(current ? [current] : []), ...pending]),
  );
  const stages: LoadingStageChip[] = knownIds.map((id) => {
    if (completed.includes(id)) return { id, label: formatStageId(id), state: "completed" as const };
    if (id === current) return { id, label: formatStageId(id), state: "current" as const };
    return { id, label: formatStageId(id), state: "pending" as const };
  });

  const hasNumericProgress =
    typeof status.overall_progress === "number" && Number.isFinite(status.overall_progress);

  return {
    brand: "Aligner Studio",
    title: status.user_message || formatStageId(current || "PROCESSING"),
    detail: hasNumericProgress
      ? `${Math.max(0, Math.min(100, Math.round(status.overall_progress)))}% from server`
      : "Waiting for server progress",
    mode: hasNumericProgress ? "determinate" : "indeterminate",
    progressPercent: hasNumericProgress
      ? Math.max(0, Math.min(100, Math.round(status.overall_progress)))
      : null,
    elapsedSeconds:
      typeof status.elapsed_seconds === "number" && Number.isFinite(status.elapsed_seconds)
        ? status.elapsed_seconds
        : null,
    remainingLabel: presentRemainingTime(status.remaining_time).label,
    currentStageId: current ?? null,
    stages,
    source: "backend-processing",
  };
}

/** Local busy activity with no known percentage — never invent progress. */
export function loadingFromLocalActivity(activity: string): LoadingPresentation {
  return {
    brand: "Aligner Studio",
    title: activity,
    detail: "Waiting for response",
    mode: "indeterminate",
    progressPercent: null,
    elapsedSeconds: null,
    remainingLabel: NO_RELIABLE_REMAINING_TIME,
    currentStageId: null,
    stages: [],
    source: "local-activity",
  };
}

export interface ResolveLoadingInput {
  processingStatus: ProcessingStatus | null;
  isBusy: boolean;
  busyActivity: string | null;
  recalculationState: "idle" | "recalculating" | "complete";
}

/**
 * Prefer backend processing status when active.
 * Fall back to local activity labels without fabricating percentages.
 */
export function resolveLoadingPresentation(input: ResolveLoadingInput): LoadingPresentation | null {
  const status = input.processingStatus;
  if (status?.stage_status === "PROCESSING") {
    return loadingFromProcessingStatus(status);
  }
  // Keep the branded overlay while the completed job's treatment payload is fetched.
  if (status?.stage_status === "COMPLETED" && input.isBusy) {
    return loadingFromProcessingStatus(status);
  }
  if (input.recalculationState === "recalculating") {
    return loadingFromLocalActivity("Recalculating treatment plan");
  }
  if (input.isBusy && input.busyActivity) {
    return loadingFromLocalActivity(input.busyActivity);
  }
  return null;
}
