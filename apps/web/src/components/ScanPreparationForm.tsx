import { useState } from "react";
import type { PreparationJob, PreparationState } from "@alignerstudio/contracts";
import { formatPreparationReadiness, preparationNextStep } from "../caseIntake";

export interface PreparationRequest {
  action: "preview" | "apply" | "undo" | "reset" | "accept";
  operation?: string;
  parameters?: Record<string, unknown>;
}

export interface PreparationPreview {
  preview?: boolean;
  persisted?: boolean;
  operation?: string;
  limitations?: string;
  truth_state?: string;
  clinical_axes?: boolean;
  components?: Array<{ id: number; face_count: number; vertex_count?: number }>;
  quality_comparison?: PreparationState["quality_comparison"];
}

interface ScanPreparationFormProps {
  arch: "upper" | "lower";
  preparation: PreparationState | null | undefined;
  sourceVertexCount?: number;
  sourceFaceCount?: number;
  preview: PreparationPreview | null;
  activeJob?: PreparationJob | null;
  disabled: boolean;
  onPrepare: (arch: "upper" | "lower", request: PreparationRequest) => void;
  onDismissPreview: () => void;
  onCancelJob?: () => void;
}

function parseBox(values: string[]): number[] | null {
  if (values.length !== 6) return null;
  const numbers = values.map((value) => Number(value));
  if (numbers.some((value) => !Number.isFinite(value))) return null;
  return numbers;
}

/** Preparation actions stay on the intake form. The inspector only reports status. */
export function ScanPreparationForm({
  arch,
  preparation,
  sourceVertexCount,
  sourceFaceCount,
  preview,
  activeJob = null,
  disabled,
  onPrepare,
  onDismissPreview,
  onCancelJob,
}: ScanPreparationFormProps): JSX.Element {
  const [box, setBox] = useState(["", "", "", "", "", ""]);
  const [componentIds, setComponentIds] = useState("");
  const readiness = formatPreparationReadiness(preparation?.readiness);
  const prepared = preparation?.quality_comparison?.prepared;
  const warnings = prepared?.warnings ?? [];
  const history = preparation?.operations ?? [];
  const region = parseBox(box);
  const ids = componentIds
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .map((item) => Number(item));
  const idsReady = ids.length > 0 && ids.every((item) => Number.isInteger(item));
  const jobActive = activeJob?.state === "queued" || activeJob?.state === "running";
  const controlsDisabled = disabled || jobActive;
  const elapsed =
    typeof activeJob?.duration_ms === "number" && Number.isFinite(activeJob.duration_ms)
      ? activeJob.duration_ms < 10000
        ? `${(activeJob.duration_ms / 1000).toFixed(1)}s`
        : `${Math.round(activeJob.duration_ms / 1000)}s`
      : "";
  const progress =
    typeof activeJob?.progress === "number" && Number.isFinite(activeJob.progress)
      ? `${Math.round(activeJob.progress * 100)}%`
      : "";

  return (
    <div className="scan-preparation" data-testid={`${arch}-preparation`}>
      <p data-testid={`${arch}-preparation-status`}>
        Preparation {readiness}. {preparationNextStep(readiness)}
      </p>
      <small>
        Source {sourceVertexCount ?? "?"} vertices · {sourceFaceCount ?? "?"} faces
        {prepared
          ? ` · Prepared ${prepared.vertex_count ?? "?"} vertices · ${prepared.face_count ?? "?"} faces`
          : " · No prepared mesh"}
      </small>
      {warnings.length > 0 ? <small>{warnings.join(", ")}</small> : null}
      <small data-testid={`${arch}-preparation-history`}>
        {history.length
          ? history.map((item) => `${item.operation ?? "step"} ${item.truth_state ?? ""}`.trim()).join(" → ")
          : "No preparation steps."}
      </small>
      {activeJob ? (
        <small data-testid={`${arch}-preparation-job`}>
          {activeJob.operation ?? "preparation"} {activeJob.state ?? "queued"}
          {progress ? ` · ${progress}` : ""}
          {elapsed ? ` · ${elapsed}` : ""}
          {activeJob.source_artifact_hash ? ` · source ${activeJob.source_artifact_hash.slice(0, 12)}` : ""}
          {activeJob.output_artifact_hash
            ? ` → derived ${activeJob.output_artifact_hash.slice(0, 12)}`
            : jobActive
              ? " → derived pending"
              : ""}
          {activeJob.state === "failed" ? ` · ${activeJob.error?.message ?? "Preparation failed."}` : ""}
          {activeJob.cache_hit ? " · reused" : ""}
        </small>
      ) : null}
      {jobActive && onCancelJob ? (
        <button type="button" className="text-button" onClick={onCancelJob} data-testid={`${arch}-preparation-cancel-job`}>
          Cancel job
        </button>
      ) : null}
      <small>
        Standard views and fit stay on the viewport toolbar. They do not rotate the scan.
        Geometric PCA is not a clinical axis. A derived mesh is not observed anatomy. FDI is not assigned.
      </small>
      <div className="cad-quick-actions">
        <button
          type="button"
          className="text-button"
          disabled={controlsDisabled}
          onClick={() =>
            onPrepare(arch, {
              action: "preview",
              operation: "orient",
              parameters: {
                method: "user_transform",
                rotation_deg: [0, 0, 90],
                translation: [0, 0, 0],
              },
            })
          }
        >
          Preview 90° Z
        </button>
        <button
          type="button"
          className="text-button"
          disabled={controlsDisabled}
          onClick={() =>
            onPrepare(arch, {
              action: "apply",
              operation: "orient",
              parameters: {
                method: "user_transform",
                rotation_deg: [0, 0, 90],
                translation: [0, 0, 0],
              },
            })
          }
        >
          Rotate 90° Z
        </button>
        <button
          type="button"
          className="text-button"
          disabled={controlsDisabled}
          onClick={() =>
            onPrepare(arch, {
              action: "apply",
              operation: "orient",
              parameters: {
                method: "user_transform",
                rotation_deg: [0, 0, 0],
                translation: [1, 0, 0],
              },
            })
          }
        >
          Translate +1 X
        </button>
        <button
          type="button"
          className="text-button"
          disabled={controlsDisabled}
          onClick={() =>
            onPrepare(arch, {
              action: "apply",
              operation: "orient",
              parameters: { method: "vertex_pca" },
            })
          }
        >
          Geometric PCA
        </button>
        <button
          type="button"
          className="text-button"
          disabled={controlsDisabled}
          onClick={() =>
            onPrepare(arch, {
              action: "apply",
              operation: "cleanup",
              parameters: {
                merge_duplicate_vertices: true,
                remove_degenerate_faces: true,
                remove_duplicate_faces: true,
                remove_invalid_components: true,
              },
            })
          }
        >
          Safe cleanup
        </button>
        <button type="button" className="text-button" disabled={controlsDisabled || history.length === 0} onClick={() => onPrepare(arch, { action: "undo" })}>
          Undo
        </button>
        <button type="button" className="text-button" disabled={controlsDisabled || readiness === "NOT_PREPARED"} onClick={() => onPrepare(arch, { action: "reset" })}>
          Reset
        </button>
        <button type="button" className="text-button" disabled={controlsDisabled || readiness === "BLOCKED"} onClick={() => onPrepare(arch, { action: "accept" })}>
          Accept for segmentation
        </button>
      </div>
      <label htmlFor={`${arch}-trim-box`}>Trim box min x, y, z then max x, y, z</label>
      <input
        id={`${arch}-trim-box`}
        value={box.join(" ")}
        disabled={controlsDisabled}
        placeholder="-1 -1 -1 1 1 1"
        onChange={(event) => {
          const parts = event.target.value.trim().split(/\s+/);
          setBox([0, 1, 2, 3, 4, 5].map((index) => parts[index] ?? ""));
        }}
      />
      <div className="cad-quick-actions">
        <button
          type="button"
          className="text-button"
          disabled={controlsDisabled || region === null}
          onClick={() =>
            region &&
            onPrepare(arch, {
              action: "preview",
              operation: "trim",
              parameters: {
                region: "axis_aligned_box",
                minimum: region.slice(0, 3),
                maximum: region.slice(3),
              },
            })
          }
        >
          Preview trim
        </button>
        <button
          type="button"
          className="text-button"
          disabled={controlsDisabled || region === null}
          onClick={() =>
            region &&
            onPrepare(arch, {
              action: "apply",
              operation: "trim",
              parameters: {
                region: "axis_aligned_box",
                minimum: region.slice(0, 3),
                maximum: region.slice(3),
              },
            })
          }
        >
          Apply trim
        </button>
        <button type="button" className="text-button" disabled={!preview} onClick={onDismissPreview}>
          Cancel preview
        </button>
      </div>
      {preview ? (
        <small data-testid={`${arch}-preparation-preview`}>
          Preview only. {preview.limitations ?? "Nothing was written."} Clinical axes{" "}
          {preview.clinical_axes ? "were set" : "were not set"}.
          {preview.components?.length
            ? ` Components: ${preview.components.map((item) => `${item.id} (${item.face_count} faces)`).join(", ")}.`
            : ""}
        </small>
      ) : null}
      <div className="cad-quick-actions">
        <button
          type="button"
          className="text-button"
          disabled={controlsDisabled}
          onClick={() =>
            onPrepare(arch, {
              action: "preview",
              operation: "components",
              parameters: { action: "list" },
            })
          }
        >
          List components
        </button>
        <label htmlFor={`${arch}-component-ids`}>Component ids</label>
        <input
          id={`${arch}-component-ids`}
          value={componentIds}
          disabled={controlsDisabled}
          placeholder="1"
          onChange={(event) => setComponentIds(event.target.value)}
        />
        <button
          type="button"
          className="text-button"
          disabled={controlsDisabled || !idsReady}
          onClick={() =>
            onPrepare(arch, {
              action: "apply",
              operation: "components",
              parameters: {
                action: "remove",
                component_ids: ids,
                user_marked_irrelevant: false,
              },
            })
          }
        >
          Remove selected components
        </button>
      </div>
    </div>
  );
}
