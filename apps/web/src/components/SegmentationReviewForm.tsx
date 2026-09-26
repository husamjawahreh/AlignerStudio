import type { SegmentationJob, SegmentationState } from "@alignerstudio/contracts";

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
  if (!ACCEPTED.has(readiness ?? "")) return null;
  const active = job?.state === "queued" || job?.state === "running";
  const blocked = Boolean(job?.blocked || segmentation?.active_run?.status === "blocked");
  const instances = segmentation?.review?.instances ?? [];
  const identity = segmentation?.semantic_identity ?? job?.semantic_identity ?? "NOT_ESTABLISHED";
  const realInference = Boolean(job?.real_inference || segmentation?.active_run?.real_inference);
  const completed = job?.state === "completed" || segmentation?.active_run?.status === "completed";
  const genuine = !blocked && realInference && completed && instances.length > 0;
  const outcome = genuine
    ? "SEGMENTATION_COMPLETED"
    : blocked
      ? "ENVIRONMENT_BLOCKED"
      : "SEGMENTATION_NOT_RUN";
  const selfTest = job?.self_test_state ?? segmentation?.self_test_state ?? "not probed";
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
      <p data-testid={`${arch}-segmentation-outcome`}>{outcome}</p>
      <p data-testid={`${arch}-segmentation-provenance`}>
        Semantic identity {identity}. Self-test {selfTest}. QUALITY_EVALUATION NOT_AVAILABLE. Split
        is unavailable. Manual segmentation correction is not available and does not replace the
        model. {realInference ? "Real inference recorded." : "Real inference not claimed."} Clinical
        accuracy is not established. Validation{" "}
        {segmentation?.active_run?.validation_status ?? job?.validation_status ?? "NOT_AVAILABLE"}.
        Evidence {shortHash(segmentation?.active_run?.evidence_bundle_sha256 ?? job?.evidence_bundle_sha256)}.
        Execution origin {segmentation?.active_run?.execution_origin ?? job?.execution_origin ?? "UNKNOWN"}.
        {segmentation?.active_run?.execution_origin === "EXTERNAL_CUDA"
          ? "External CUDA is not local native execution."
          : ""}
        Doctor acceptance is not clinical verification.
      </p>
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
              {genuine ? (
                <button
                  type="button"
                  className="text-button"
                  onClick={() => onReview({ action: "select", instance_id: instance.instance_id })}
                >
                  {instance.instance_id}
                </button>
              ) : (
                <span>{instance.instance_id}</span>
              )}
              <small>
                {instance.review_state} · {instance.truth_state} ·{" "}
                {instance.model_class_label ?? "model-defined class"} {instance.raw_model_class ?? "none"} ·
                mapping {instance.model_class_mapping ?? "NOT_ESTABLISHED"}
                {instance.confidence_available
                  ? ` · model confidence ${instance.confidence}`
                  : " · model confidence NOT_AVAILABLE"}
                {instance.real_inference ? "" : " · mock contract is not real inference"}
                {instance.fdi == null ? " · FDI not assigned" : ""}
                {instance.visible === false ? " · hidden" : ""}
              </small>
              {genuine ? (
                <>
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
                </>
              ) : null}
            </div>
          ))
        )}
      </div>
      {genuine && instances.length >= 2 ? (
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
      <p data-testid={`${arch}-segmentation-split`}>SPLIT_UNAVAILABLE</p>
      {genuine ? (
      <div className="cad-quick-actions">
        <button type="button" className="text-button" disabled={disabled || instances.length === 0} onClick={() => onReview({ action: "undo" })}>
          Undo review
        </button>
        <button type="button" className="text-button" disabled={disabled || instances.length === 0} onClick={() => onReview({ action: "reset" })}>
          Reset review
        </button>
      </div>
      ) : null}
    </section>
  );
}
