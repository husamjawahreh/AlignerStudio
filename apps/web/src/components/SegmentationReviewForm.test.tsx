import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SegmentationReviewForm } from "./SegmentationReviewForm";

const candidate = {
  availability: "AVAILABLE",
  capability_state: "AVAILABLE",
  semantic_identity: "NOT_ESTABLISHED",
  fdi_assigned: false,
  clinically_segmented: false,
  clinical_accuracy_claim: false,
  active_run: {
    run_id: "run-1",
    status: "completed",
    reviewable: true,
    real_inference: false,
    prepared_sha256: "abc123prepared",
    source_sha256: "def456source",
    inference_kind: "mock_contract",
    semantic_identity: "NOT_ESTABLISHED",
  },
  review: {
    run_id: "run-1",
    instances: [
      {
        instance_id: "inst-0",
        raw_model_class: 0,
        model_class_label: "model-defined class",
        model_class_mapping: "NOT_ESTABLISHED",
        truth_state: "PREDICTED",
        review_state: "MODEL_PREDICTION",
        visible: true,
        fdi: null,
        real_inference: false,
        confidence: null,
        confidence_available: false,
      },
    ],
  },
};

describe("SegmentationReviewForm", () => {
  it("states unresolved identity and does not render before acceptance", () => {
    const { rerender } = render(
      <SegmentationReviewForm
        arch="upper"
        readiness="PREPARED"
        onStart={vi.fn()}
        onReview={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("upper-segmentation-review")).toBeNull();
    rerender(
      <SegmentationReviewForm
        arch="upper"
        readiness="READY_WITH_WARNINGS"
        segmentation={candidate}
        onStart={vi.fn()}
        onReview={vi.fn()}
      />,
    );
    expect(screen.getByTestId("upper-segmentation-identity").textContent).toContain("NOT_ESTABLISHED");
    expect(screen.getByTestId("upper-segmentation-identity").textContent).toMatch(/not established/i);
    expect(screen.getByText(/FDI not assigned/)).toBeTruthy();
    expect(screen.getByText(/mock contract is not real inference/)).toBeTruthy();
    expect(screen.getByText(/MODEL_PREDICTION/)).toBeTruthy();
    expect(screen.getByTestId("upper-segmentation-outcome").textContent).toBe("SEGMENTATION_NOT_RUN");
    expect(screen.queryByRole("button", { name: "Accept candidate" })).toBeNull();
    expect(screen.getByTestId("upper-segmentation-provenance").textContent).toContain(
      "QUALITY_EVALUATION NOT_AVAILABLE",
    );
    expect(screen.getByTestId("upper-segmentation-split").textContent).toBe("SPLIT_UNAVAILABLE");
  });

  it("shows a blocked runtime without a candidate", () => {
    render(
      <SegmentationReviewForm
        arch="upper"
        readiness="READY_WITH_WARNINGS"
        segmentation={{
          availability: "ENVIRONMENT_BLOCKED",
          capability_state: "DRIVER_UNAVAILABLE",
          semantic_identity: "NOT_ESTABLISHED",
          fdi_assigned: false,
          clinically_segmented: false,
          active_run: {
            status: "blocked",
            real_inference: false,
            semantic_identity: "NOT_ESTABLISHED",
            blocker: { code: "DRIVER_UNAVAILABLE", availability: "ENVIRONMENT_BLOCKED" },
          },
          review: { instances: [], reason: "No segmentation candidate was produced." },
        }}
        job={{
          job_id: "job-1",
          state: "failed",
          blocked: true,
          backend: "toothinstancenet",
          real_inference: false,
          semantic_identity: "NOT_ESTABLISHED",
          fdi_assigned: false,
          clinically_segmented: false,
          source_sha256: "source-hash",
          prepared_input_sha: "prepared-hash",
          error: {
            code: "DRIVER_UNAVAILABLE",
            message: "ToothInstanceNet cannot execute.",
            availability: "ENVIRONMENT_BLOCKED",
          },
        }}
        onStart={vi.fn()}
        onReview={vi.fn()}
      />,
    );
    expect(screen.getByTestId("upper-segmentation-status").textContent).toContain("blocked");
    expect(screen.getByTestId("upper-segmentation-status").textContent).toContain("DRIVER_UNAVAILABLE");
    expect(screen.getByTestId("upper-segmentation-job").textContent).toContain("ENVIRONMENT_BLOCKED");
    expect(screen.getByTestId("upper-segmentation-outcome").textContent).toBe("ENVIRONMENT_BLOCKED");
    expect(screen.getByTestId("upper-segmentation-outcome").textContent).not.toContain(
      "SEGMENTATION_COMPLETED",
    );
    expect(screen.getByTestId("upper-segmentation-identity").textContent).toContain("NOT_ESTABLISHED");
    expect(screen.getByTestId("upper-segmentation-provenance").textContent).toContain(
      "QUALITY_EVALUATION NOT_AVAILABLE",
    );
    expect(screen.getByTestId("upper-segmentation-provenance").textContent).toContain(
      "Real inference not claimed",
    );
    expect(screen.getByText(/No segmentation candidate/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Accept candidate" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Merge first two" })).toBeNull();
  });

  it("disables a second start and hides review controls while inference is not genuine", () => {
    const onStart = vi.fn();
    const onReview = vi.fn();
    render(
      <SegmentationReviewForm
        arch="upper"
        readiness="READY_FOR_SEGMENTATION"
        segmentation={candidate}
        job={{ job_id: "job-1", state: "running", progress: 0.45, backend: "toothinstancenet" }}
        onStart={onStart}
        onReview={onReview}
      />,
    );
    expect(screen.getByRole("button", { name: "Start segmentation" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Accept candidate" })).toBeNull();
    expect(onStart).not.toHaveBeenCalled();
    expect(onReview).not.toHaveBeenCalled();
  });

  it("shows review controls only for a genuine completed inference", () => {
    const onReview = vi.fn();
    render(
      <SegmentationReviewForm
        arch="upper"
        readiness="READY_FOR_SEGMENTATION"
        segmentation={{
          ...candidate,
          active_run: { ...candidate.active_run, real_inference: true, status: "completed" },
          review: {
            ...candidate.review,
            instances: [{ ...candidate.review.instances[0], real_inference: true }],
          },
        }}
        job={{
          job_id: "job-real",
          state: "completed",
          blocked: false,
          real_inference: true,
          backend: "toothinstancenet",
          self_test_state: "READY_FOR_INFERENCE",
        }}
        onStart={vi.fn()}
        onReview={onReview}
      />,
    );
    expect(screen.getByTestId("upper-segmentation-outcome").textContent).toBe(
      "SEGMENTATION_COMPLETED",
    );
    expect(screen.getByTestId("upper-segmentation-provenance").textContent).toContain(
      "NOT_ESTABLISHED",
    );
    expect(screen.getByTestId("upper-segmentation-provenance").textContent).toContain(
      "QUALITY_EVALUATION NOT_AVAILABLE",
    );
    fireEvent.click(screen.getByRole("button", { name: "Accept candidate" }));
    expect(onReview).toHaveBeenCalledWith({ action: "accept", instance_id: "inst-0" });
  });
});
