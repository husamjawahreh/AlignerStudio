import type { SegmentationJob, SegmentationState } from "@alignerstudio/contracts";
import { useState } from "react";

const ACCEPTED = new Set(["READY_FOR_SEGMENTATION", "READY_WITH_WARNINGS"]);

export interface SegmentationReviewRequest {
  action: string;
  instance_id?: string;
  other_instance_id?: string;
  face_indices?: number[];
}

interface SegmentationReviewFormProps {
  arch: "upper" | "lower";
  readiness?: string | null;
  segmentation?: SegmentationState | null;
  job?: SegmentationJob | null;
  disabled?: boolean;
  onStart: () => void;
  onReview: (request: SegmentationReviewRequest) => void;
}

function shortHash(value?: string | null): string {
  if (!value) return "pending";
  return value.slice(0, 12);
}

export function SegmentationReviewForm({
  arch,
  readiness,
  segmentation,
  job,
  disabled = false,
  onStart,
  onReview,
}: SegmentationReviewFormProps) {
  const [faceText, setFaceText] = useState("");
  if (!ACCEPTED.has(readiness ?? "")) return null;
  const active = job?.state === "queued" || job?.state === "running";
  const blocked = Boolean(job?.blocked || segmentation?.active_run?.status === "blocked");
  const instances = segmentation?.review?.instances ?? [];
  const selected = segmentation?.review?.selected_instance_id ?? instances[0]?.instance_id ?? "";
  const identity = segmentation?.semantic_identity ?? job?.semantic_identity ?? "NOT_ESTABLISHED";
  const status = blocked
    ? `blocked ${job?.error?.code ?? segmentation?.capability_state ?? ""}`.trim()
    : job
      ? `${job.backend ?? "segmentation"} ${job.state ?? "queued"}`
      : "not started";
  return (
    <section className="segmentation-review" data-testid={`${arch}-segmentation-review`}>
      <p data-testid={`${arch}-segmentation-identity`}>
        Model-derived segmentation. Semantic identity is {identity}. Clinical tooth identity is not
        established. Review is required. This is not clinical validation or an FDI assignment.
      </p>
      <p data-testid={`${arch}-segmentation-status`}>{status}</p>
      {job ? (
        <p data-testid={`${arch}-segmentation-job`}>
          {job.backend ?? "backend"} {job.state}
          {typeof job.progress === "number" ? ` ${Math.round(job.progress * 100)}%` : ""}
          {typeof job.duration_ms === "number" ? ` ${Math.round(job.duration_ms)} ms` : ""}
          {` source ${shortHash(job.source_sha256)} → prepared ${shortHash(job.prepared_input_sha)}`}
          {job.output_run_id ? ` run ${job.output_run_id.slice(0, 8)}` : ""}
          {job.real_inference ? "" : " real inference not claimed"}
          {blocked ? ` ${job.error?.availability ?? segmentation?.availability ?? "ENVIRONMENT_BLOCKED"}` : ""}
          {job.error?.message ? ` ${job.error.message}` : ""}
        </p>
      ) : null}
      <div className="cad-quick-actions">
        <button
          type="button"
          className="text-button"
          disabled={disabled || active}
          onClick={onStart}
        >
          Start segmentation
        </button>
      </div>
      <div data-testid={`${arch}-segmentation-instances`}>
        {instances.length === 0 ? (
          <small>
            {blocked
              ? "No segmentation candidate. Review cannot assign tooth identity."
              : "No instance is available until a segmentation candidate exists."}
          </small>
        ) : (
          instances.map((instance) => (
            <div key={instance.instance_id}>
              <button
                type="button"
                className="text-button"
                onClick={() => onReview({ action: "select", instance_id: instance.instance_id })}
              >
                {instance.instance_id}
              </button>
              <small>
                {instance.review_state} · {instance.truth_state} ·{" "}
                {instance.model_class_label ?? "model-defined class"} {instance.raw_model_class ?? "none"} ·
                mapping {instance.model_class_mapping ?? "NOT_ESTABLISHED"}
                {instance.real_inference ? "" : " · mock contract is not real inference"}
                {instance.fdi == null ? " · FDI not assigned" : ""}
                {instance.visible === false ? " · hidden" : ""}
              </small>
              <button
                type="button"
                className="text-button"
                disabled={disabled}
                onClick={() =>
                  onReview({
                    action: instance.visible === false ? "show" : "hide",
                    instance_id: instance.instance_id,
                  })
                }
              >
                {instance.visible === false ? "Show" : "Hide"}
              </button>
              <button
                type="button"
                className="text-button"
                disabled={disabled}
                onClick={() => onReview({ action: "mark_review", instance_id: instance.instance_id })}
              >
                Mark for review
              </button>
              <button
                type="button"
                className="text-button"
                disabled={disabled}
                onClick={() => onReview({ action: "accept", instance_id: instance.instance_id })}
              >
                Accept candidate
              </button>
              <button
                type="button"
                className="text-button"
                disabled={disabled}
                onClick={() => onReview({ action: "reject", instance_id: instance.instance_id })}
              >
                Reject candidate
              </button>
            </div>
          ))
        )}
      </div>
      {instances.length >= 2 ? (
        <button
          type="button"
          className="text-button"
          disabled={disabled}
          onClick={() =>
            onReview({
              action: "merge",
              instance_id: instances[0].instance_id,
              other_instance_id: instances[1].instance_id,
            })
          }
        >
          Merge first two
        </button>
      ) : null}
      {selected && instances.length > 0 ? (
        <div className="cad-quick-actions">
          <label htmlFor={`${arch}-split-faces`}>Split face indices</label>
          <input
            id={`${arch}-split-faces`}
            value={faceText}
            disabled={disabled}
            placeholder="0 1 2"
            onChange={(event) => setFaceText(event.target.value)}
          />
          <button
            type="button"
            className="text-button"
            disabled={disabled}
            onClick={() =>
              onReview({
                action: "split",
                instance_id: selected,
                face_indices: faceText
                  .trim()
                  .split(/\s+/)
                  .filter(Boolean)
                  .map((item) => Number(item)),
              })
            }
          >
            Split instance
          </button>
        </div>
      ) : null}
      <div className="cad-quick-actions">
        <button type="button" className="text-button" disabled={disabled || instances.length === 0} onClick={() => onReview({ action: "undo" })}>
          Undo review
        </button>
        <button type="button" className="text-button" disabled={disabled || instances.length === 0} onClick={() => onReview({ action: "reset" })}>
          Reset review
        </button>
      </div>
    </section>
  );
}
