import type { CaseDentalIntelligencePayload, IntelligenceTruthState } from "@alignerstudio/contracts";
import type { MovementSummary, ReviewToothMesh } from "../review/types";
import { FixtureBadge } from "./FixtureBadge";
import { formatTruthState } from "../analysisPresentation";
import type { ToothInteractionState } from "../viewer/toothInteraction";
import { canTransformTooth } from "../viewer/toothInteraction";

interface InspectionPanelProps {
  tooth: ReviewToothMesh | null;
  dentalIntelligence?: CaseDentalIntelligencePayload | null;
  draftMovement?: MovementSummary | null;
  originalMovement?: MovementSummary | null;
  isDirty?: boolean;
  interactionState?: ToothInteractionState | null;
  onDraftChange?: (movement: MovementSummary) => void;
  onApply?: () => void;
  onCancel?: () => void;
  onReset?: () => void;
  onToggleLocked?: () => void;
  onToggleExcluded?: () => void;
  onUndo?: () => void;
  onRedo?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
}

type NumericMovementKey =
  | "translationX"
  | "translationY"
  | "translationZ"
  | "rotation"
  | "tip"
  | "torque"
  | "angulation"
  | "intrusion"
  | "extrusion";

const movementRows: readonly [NumericMovementKey, string, string][] = [
  ["translationX", "Translation X", "mm"],
  ["translationY", "Translation Y", "mm"],
  ["translationZ", "Translation Z", "mm"],
  ["rotation", "Rotation", "°"],
  ["tip", "Tip", "°"],
  ["torque", "Torque", "°"],
  ["angulation", "Angulation", "°"],
  ["intrusion", "Intrusion", "mm"],
  ["extrusion", "Extrusion", "mm"],
];

function findToothIntelligence(
  dentalIntelligence: CaseDentalIntelligencePayload | null | undefined,
  tooth: ReviewToothMesh,
) {
  return dentalIntelligence?.teeth.find(
    (item) =>
      (tooth.toothRef != null && item.tooth_ref === tooth.toothRef) ||
      (item.instance_id === tooth.instanceId && item.arch === tooth.arch),
  );
}

export function InspectionPanel({
  tooth,
  dentalIntelligence = null,
  draftMovement,
  originalMovement,
  isDirty = false,
  interactionState = null,
  onDraftChange,
  onApply,
  onCancel,
  onReset,
  onToggleLocked,
  onToggleExcluded,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
}: InspectionPanelProps): JSX.Element {
  if (!tooth) {
    return (
      <aside className="inspection-panel empty-panel" data-testid="inspection-panel">
        <span className="eyebrow">Tooth inspection</span>
        <h2>Select a tooth</h2>
        <p>
          Choose an individual mesh in the viewport to inspect its read-only proposal and validation
          state.
        </p>
      </aside>
    );
  }

  const toothIntel = findToothIntelligence(dentalIntelligence, tooth);
  const fdiState: IntelligenceTruthState | null = toothIntel?.fdi_number.state ?? null;
  const geometryState = toothIntel?.geometry.state ?? null;
  const axesState = toothIntel?.clinical_dental_axes.state ?? null;
  const landmarksState = toothIntel?.landmarks.state ?? null;
  const rootsState = toothIntel?.root_geometry.state ?? null;
  const overallState = toothIntel?.overall_truth_state ?? null;
  const transformAllowed = canTransformTooth(draftMovement);

  return (
    <aside className="inspection-panel" data-testid="inspection-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Tooth inspection</span>
          <h2>{tooth.fdiNumber ? `FDI ${tooth.fdiNumber}` : tooth.toothRef ?? "Semantic tooth"}</h2>
        </div>
        <span
          className={`status-dot ${tooth.validationStatus}`}
          aria-label={tooth.validationStatus}
        />
      </div>
      <FixtureBadge fixture={tooth.fixture} provenance={tooth.provenance} />
      <div className="inspection-meta">
        <span data-testid="inspection-tooth-ref">
          Ref {tooth.toothRef ?? `instance:${tooth.instanceId}`}
        </span>
        <span>{tooth.arch} arch</span>
        {tooth.semanticLabel !== null && tooth.semanticLabel !== undefined && (
          <span>Semantic label {tooth.semanticLabel}</span>
        )}
        <span data-testid="inspection-fdi-truth">
          FDI:{" "}
          {tooth.fdiNumber != null
            ? `${tooth.fdiNumber} · ${formatTruthState(fdiState ?? "requires_review")}`
            : formatTruthState("not_available")}
        </span>
        {tooth.confidence > 0 && (
          <span>Identification confidence {(tooth.confidence * 100).toFixed(0)}%</span>
        )}
        {tooth.confidence === 0 && (
          <span>Identification confidence: Not Available</span>
        )}
      </div>
      {interactionState && (
        <div className="inspection-status" data-testid="inspection-interaction">
          <span>Interaction</span>
          <strong data-testid="interaction-phase">{interactionState.phase.replaceAll("_", " ")}</strong>
          <p data-testid="interaction-coordinate-space">
            Coordinate space · {interactionState.coordinateSpace.replaceAll("_", " ")}
          </p>
          <p data-testid="interaction-constraints">
            Constraints · {interactionState.constraintAvailability.replaceAll("_", " ")}
          </p>
          <p>Transform · {transformAllowed ? "geometrically editable" : "blocked (lock/exclude)"}</p>
          {interactionState.notes.map((note) => (
            <p key={note}>{note}</p>
          ))}
        </div>
      )}

      {(overallState || geometryState || axesState || landmarksState || rootsState) && (
        <div className="inspection-status" data-testid="inspection-intelligence">
          <span>Intelligence</span>
          {overallState && <strong>Overall · {formatTruthState(overallState)}</strong>}
          {geometryState && <p>Geometry · {formatTruthState(geometryState)}</p>}
          {landmarksState && <p>Landmarks · {formatTruthState(landmarksState)}</p>}
          {axesState && (
            <p>
              Clinical dental axes · {formatTruthState(axesState)}
              {axesState === "not_available" ? " (mesh PCA is not a clinical axis)" : ""}
            </p>
          )}
          {rootsState && <p>Root geometry · {formatTruthState(rootsState)}</p>}
          {toothIntel?.source_mesh_sha256 && (
            <p>Source mesh · {toothIntel.source_mesh_sha256.slice(0, 12)}…</p>
          )}
        </div>
      )}

      <div className="inspection-status">
        <span>Validation</span>
        <strong>{tooth.validationStatus}</strong>
        <p>{tooth.validationMessage || "No validation message for this tooth."}</p>
      </div>
      <div className="movement-list">
        <div className="section-label">Proposed movement</div>
        {movementRows.map(([key, label, unit]) => (
          <div className="movement-row" key={key}>
            <span>{label}</span>
            {draftMovement && onDraftChange ? (
              <label className="movement-input-wrap">
                <input
                  aria-label={label}
                  type="number"
                  step="0.01"
                  value={draftMovement[key] ?? 0}
                  disabled={!transformAllowed}
                  onChange={(event) =>
                    onDraftChange({ ...draftMovement, [key]: Number(event.target.value) })
                  }
                />
                <small>{unit}</small>
              </label>
            ) : (
              <strong>
                {(tooth.movement[key] ?? 0).toFixed(2)} {unit}
              </strong>
            )}
          </div>
        ))}
      </div>
      <div className="inspection-status">
        <span>Stage rate</span>
        <strong>{tooth.rate ? formatMovement(tooth.rate) : "Unavailable"}</strong>
        <span>Accumulated</span>
        <strong>
          {tooth.accumulated ? formatMovement(tooth.accumulated) : formatMovement(tooth.movement)}
        </strong>
        <span>Constraints</span>
        <strong>{tooth.limitStatus?.replaceAll("_", " ") ?? "not configured"}</strong>
      </div>
      {draftMovement && onApply && onCancel && onReset ? (
        <>
          <div className={`edit-state ${isDirty ? "is-dirty" : ""}`}>
            {isDirty ? "Unsaved doctor edits" : "No unsaved edits"}
          </div>
          <div className="edit-actions">
            <button className="secondary-button" onClick={onCancel} disabled={!isDirty}>
              Cancel
            </button>
            <button className="secondary-button" onClick={onReset}>
              Reset tooth
            </button>
            <button className="primary-button" onClick={onApply} disabled={!isDirty}>
              Apply
            </button>
          </div>
          <div className="edit-actions">
            <button className="secondary-button" onClick={onToggleLocked}>
              {draftMovement.locked ? "Unlock" : "Lock"}
            </button>
            <button className="secondary-button" onClick={onToggleExcluded}>
              {draftMovement.excluded ? "Include" : "Exclude"}
            </button>
            <button className="icon-button" onClick={onUndo} disabled={!canUndo} aria-label="Undo doctor edit">
              Undo
            </button>
            <button className="icon-button" onClick={onRedo} disabled={!canRedo} aria-label="Redo doctor edit">
              Redo
            </button>
          </div>
          <div className="readonly-note">
            Doctor editing is explicit and read-only until Apply. Geometric executability is not
            clinical approval. No doctor-approved state is exposed from this interaction engine.
          </div>
        </>
      ) : (
        <div className="readonly-note">
          Read-only review · editing and restaging are not available.
        </div>
      )}
      {originalMovement && (
        <div className="original-values">
          Original generated movement is preserved in the edit history.
        </div>
      )}
    </aside>
  );
}

function formatMovement(movement: MovementSummary): string {
  const total = [
    movement.translationX,
    movement.translationY,
    movement.translationZ,
    movement.rotation,
    movement.tip,
    movement.torque,
    movement.angulation ?? 0,
    movement.intrusion,
    movement.extrusion,
  ].reduce((sum, value) => sum + Math.abs(value), 0);
  return total.toFixed(2);
}
