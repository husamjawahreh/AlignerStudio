/**
 * Evidence-based remaining time. Mirrors engines/performance/remaining_time.py.
 * Elapsed time alone never becomes a percent or a countdown.
 */

export const NO_RELIABLE_REMAINING_TIME = "No reliable remaining-time estimate";

const MEASURED_SAMPLE_COUNT = 3;
const MAX_MATCHING_SAMPLES = 12;
const OUT_OF_RANGE_FACTOR = 1.25;
const MEASURED_SPREAD_LIMIT = 0.75;
const TIGHT_SPREAD = 0.35;
const RANGE_BAND_SECONDS = 30;

export type RemainingKind = "none" | "coarse" | "measured";

export interface DurationSample {
  operationId: string;
  environmentId: string;
  inputClass: string;
  durationSeconds: number;
}

export interface RemainingTimePayload {
  kind: RemainingKind;
  seconds: number | null;
  low_seconds?: number | null;
  high_seconds?: number | null;
  confidence: number | null;
  sample_count: number;
  qualifier: "none" | "estimated";
  operation_id?: string;
  environment_id?: string;
  input_class?: string;
  label: string;
  duration_class?: "fast" | "medium" | "long" | "very_long" | null;
}

export function durationClass(seconds: number): "fast" | "medium" | "long" | "very_long" {
  if (seconds < 2) return "fast";
  if (seconds < 30) return "medium";
  if (seconds < 180) return "long";
  return "very_long";
}

function percentile(sortedValues: readonly number[], fraction: number): number {
  if (sortedValues.length === 1) return sortedValues[0];
  const index = (sortedValues.length - 1) * fraction;
  const lower = Math.floor(index);
  const upper = Math.min(lower + 1, sortedValues.length - 1);
  const weight = index - lower;
  return sortedValues[lower] * (1 - weight) + sortedValues[upper] * weight;
}

function about(seconds: number): string {
  if (seconds < 90) return `About ${seconds} seconds remaining`;
  const minutes = Math.max(1, Math.round(seconds / 60));
  const unit = minutes === 1 ? "minute" : "minutes";
  return `About ${minutes} ${unit} remaining`;
}

function none(operationId: string, environmentId: string, inputClass: string, sampleCount = 0): RemainingTimePayload {
  return {
    kind: "none",
    seconds: null,
    low_seconds: null,
    high_seconds: null,
    confidence: null,
    sample_count: sampleCount,
    qualifier: "none",
    operation_id: operationId,
    environment_id: environmentId,
    input_class: inputClass,
    label: NO_RELIABLE_REMAINING_TIME,
    duration_class: null,
  };
}

export function estimateRemaining(input: {
  samples: readonly DurationSample[];
  elapsedSeconds: number | null;
  operationId: string;
  environmentId: string;
  inputClass: string;
}): RemainingTimePayload {
  const matched = input.samples
    .filter(
      (sample) =>
        sample.operationId === input.operationId &&
        sample.environmentId === input.environmentId &&
        sample.inputClass === input.inputClass &&
        Number.isFinite(sample.durationSeconds) &&
        sample.durationSeconds > 0,
    )
    .slice(-MAX_MATCHING_SAMPLES)
    .map((sample) => sample.durationSeconds);
  if (matched.length === 0 || input.elapsedSeconds == null || input.elapsedSeconds < 0) {
    return none(input.operationId, input.environmentId, input.inputClass, matched.length);
  }
  const observedMax = Math.max(...matched);
  if (input.elapsedSeconds > observedMax * OUT_OF_RANGE_FACTOR) {
    return none(input.operationId, input.environmentId, input.inputClass, matched.length);
  }
  const sorted = [...matched].sort((left, right) => left - right);
  const mid = Math.floor(sorted.length / 2);
  const center = sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  const remaining = center - input.elapsedSeconds;
  if (remaining < 1) return none(input.operationId, input.environmentId, input.inputClass, matched.length);
  const seconds = Math.round(remaining);
  if (seconds < 1) return none(input.operationId, input.environmentId, input.inputClass, matched.length);
  const spread = center ? (observedMax - Math.min(...matched)) / center : 1;
  const measured = matched.length >= MEASURED_SAMPLE_COUNT && spread <= MEASURED_SPREAD_LIMIT;
  const kind: RemainingKind = measured ? "measured" : "coarse";
  const confidence = measured ? (spread <= TIGHT_SPREAD ? 0.7 : 0.55) : matched.length >= 2 ? 0.4 : 0.3;
  const low = Math.round(Math.max(0, percentile(sorted, 0.25) - input.elapsedSeconds));
  const high = Math.round(Math.max(0, percentile(sorted, 0.75) - input.elapsedSeconds));
  let label: string;
  if (kind === "measured" && high - low >= RANGE_BAND_SECONDS && low >= 1) {
    const lowText = about(low).replace(/^About /, "").replace(/ remaining$/, "");
    const highText = about(high).replace(/^About /, "");
    label = `Estimated ${lowText} to ${highText}. Not a guarantee.`;
  } else if (kind === "measured") {
    label = `${about(seconds)}, estimated. Not a guarantee.`;
  } else {
    label = `${about(seconds)}, estimated. Uncertainty is high.`;
  }
  return {
    kind,
    seconds,
    low_seconds: kind === "measured" ? low : null,
    high_seconds: kind === "measured" ? high : null,
    confidence,
    sample_count: matched.length,
    qualifier: "estimated",
    operation_id: input.operationId,
    environment_id: input.environmentId,
    input_class: input.inputClass,
    label,
    duration_class: durationClass(center),
  };
}

/** Accept a server payload only when its own fields support the kind. */
export function presentRemainingTime(payload: RemainingTimePayload | null | undefined): RemainingTimePayload {
  if (!payload || payload.kind === "none") {
    return none(payload?.operation_id ?? "", payload?.environment_id ?? "", payload?.input_class ?? "");
  }
  const seconds = payload.seconds;
  const count = payload.sample_count;
  const coarse =
    payload.kind === "coarse" &&
    count >= 1 &&
    count < MEASURED_SAMPLE_COUNT &&
    typeof seconds === "number" &&
    seconds > 0 &&
    payload.qualifier === "estimated";
  const measured =
    payload.kind === "measured" &&
    count >= MEASURED_SAMPLE_COUNT &&
    typeof seconds === "number" &&
    seconds > 0 &&
    payload.qualifier === "estimated";
  const label = payload.label ?? "";
  const honestLabel = /estimated/i.test(label) && !/\b0 seconds\b/i.test(label) && !/guarantee exactly/i.test(label);
  if ((!coarse && !measured) || !honestLabel || label === NO_RELIABLE_REMAINING_TIME) {
    return none(payload.operation_id ?? "", payload.environment_id ?? "", payload.input_class ?? "", count);
  }
  return {
    ...payload,
    seconds,
    label,
    confidence: typeof payload.confidence === "number" ? payload.confidence : null,
  };
}
