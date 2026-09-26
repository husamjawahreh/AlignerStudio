import { describe, expect, it } from "vitest";
import { nextActionOperation, operationStartsLongWork } from "../interaction/nextAction";
import { buildFeedbackModel } from "../interaction/model";
import {
  NO_RELIABLE_REMAINING_TIME,
  durationClass,
  estimateRemaining,
  presentRemainingTime,
  type DurationSample,
} from "./remainingTime";
import { claimTerminalLoad, shouldPollProcessing } from "./processingLifecycle";

function sample(durationSeconds: number, environmentId = "test-host", inputClass = "both-arches"): DurationSample {
  return { operationId: "case-processing", environmentId, inputClass, durationSeconds };
}

describe("Wave 8 remaining time", () => {
  it("does not invent an estimate from elapsed time", () => {
    const result = estimateRemaining({
      samples: [],
      elapsedSeconds: 900,
      operationId: "case-processing",
      environmentId: "test-host",
      inputClass: "both-arches",
    });
    expect(result.kind).toBe("none");
    expect(result.seconds).toBeNull();
    expect(result.label).toBe(NO_RELIABLE_REMAINING_TIME);
    expect(result).not.toHaveProperty("overall_progress");
    expect(durationClass(1)).toBe("fast");
    expect(durationClass(10)).toBe("medium");
    expect(durationClass(60)).toBe("long");
    expect(durationClass(400)).toBe("very_long");
  });

  it("keeps one sample coarse and ignores another computer", () => {
    const result = estimateRemaining({
      samples: [sample(600), sample(600, "other-computer")],
      elapsedSeconds: 60,
      operationId: "case-processing",
      environmentId: "test-host",
      inputClass: "both-arches",
    });
    expect(result.kind).toBe("coarse");
    expect(result.sample_count).toBe(1);
    expect(result.seconds).toBe(540);
    expect(result.label).toMatch(/estimated/);
    expect(result.label).toMatch(/Uncertainty is high/);
  });

  it("uses a tight history as a measured estimate and drops out-of-range runs", () => {
    const samples = [100, 110, 120, 130].map((duration) => sample(duration));
    const measured = estimateRemaining({
      samples,
      elapsedSeconds: 40,
      operationId: "case-processing",
      environmentId: "test-host",
      inputClass: "both-arches",
    });
    expect(measured.kind).toBe("measured");
    expect(measured.seconds).toBe(75);
    expect(measured.confidence).toBe(0.7);
    expect(measured.label).toMatch(/Not a guarantee/);
    const outside = estimateRemaining({
      samples,
      elapsedSeconds: 800,
      operationId: "case-processing",
      environmentId: "test-host",
      inputClass: "both-arches",
    });
    expect(outside.kind).toBe("none");
    expect(outside.seconds).toBeNull();
  });

  it("rejects a measured payload that does not have enough samples", () => {
    const presented = presentRemainingTime({
      kind: "measured",
      seconds: 10,
      confidence: 0.9,
      sample_count: 1,
      qualifier: "estimated",
      label: "About 10 seconds remaining, estimated. Not a guarantee.",
    });
    expect(presented.kind).toBe("none");
    expect(presented.seconds).toBeNull();
  });

  it("shows the server estimate on the status line and keeps a benchmark out of the estimate", () => {
    const feedback = buildFeedbackModel({
      stageStatus: "PROCESSING",
      elapsedSeconds: 40,
      serverProgress: 40,
      benchmarkSeconds: 90,
      segmentation: null,
      operationSamples: [100, 110, 120, 130].map((duration) => sample(duration)),
      operationId: "case-processing",
      environmentId: "test-host",
      inputClass: "both-arches",
    });
    expect(feedback.progressMode).toBe("server-progress");
    expect(feedback.remainingEstimate).toBe(75);
    expect(feedback.benchmarkNote).toMatch(/not a guarantee/i);
    expect(feedback.remainingNote).not.toMatch(/^Historical sample/);
  });
});

describe("Wave 8 processing lifecycle", () => {
  it("polls only while a job is processing", () => {
    expect(shouldPollProcessing("PROCESSING")).toBe(true);
    for (const status of ["COMPLETED", "FAILED", "CANCELLED", "STALE", "INTERRUPTED", null]) {
      expect(shouldPollProcessing(status)).toBe(false);
    }
  });

  it("loads treatment once when a job completes", () => {
    const claimed = { current: null as string | null };
    expect(claimTerminalLoad(claimed, "job-1")).toBe(true);
    expect(claimTerminalLoad(claimed, "job-1")).toBe(false);
    expect(claimTerminalLoad(claimed, "job-2")).toBe(true);
  });

  it("does not treat navigation as a long operation", () => {
    expect(operationStartsLongWork(nextActionOperation("open-treatment-plan"))).toBe(false);
    expect(operationStartsLongWork(nextActionOperation("review-treatment-dependency"))).toBe(false);
    expect(operationStartsLongWork(nextActionOperation("create-treatment-plan"))).toBe(true);
    expect(operationStartsLongWork(nextActionOperation("regenerate-staging"))).toBe(true);
    expect(operationStartsLongWork(nextActionOperation("refresh-validation"))).toBe(true);
  });

  it("resolves remaining time without a scene rebuild", () => {
    const started = performance.now();
    for (let index = 0; index < 2000; index += 1) {
      estimateRemaining({
        samples: [sample(100), sample(110), sample(120)],
        elapsedSeconds: 20,
        operationId: "case-processing",
        environmentId: "test-host",
        inputClass: "both-arches",
      });
    }
    const elapsed = performance.now() - started;
    expect(elapsed).toBeLessThan(250);
  });
});
