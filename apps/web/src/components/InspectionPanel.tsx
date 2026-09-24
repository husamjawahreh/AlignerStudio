import type { MovementSummary, ReviewToothMesh } from "../review/types";
import { FixtureBadge } from "./FixtureBadge";

interface InspectionPanelProps {
  tooth: ReviewToothMesh | null;
  draftMovement?: MovementSummary | null;
  originalMovement?: MovementSummary | null;
  isDirty?: boolean;
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

export function InspectionPanel({
  tooth,
  draftMovement,
  originalMovement,
  isDirty = false,
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
      <aside className="inspection-panel empty-panel">
        <span className="eyebrow">Tooth inspection</span>
        <h2>Select a tooth</h2>
        <p>
          Choose an individual mesh in the viewport to inspect its read-only proposal and validation
          state.
        </p>
      </aside>
    );
  }

  return (
    <aside className="inspection-panel">
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
        <span>{tooth.arch} arch</span>
        {tooth.semanticLabel !== null && tooth.semanticLabel !== undefined && (
          <span>Semantic label {tooth.semanticLabel}</span>
        )}
        {!tooth.fdiNumber && <span>Experimental · no clinical FDI identity</span>}
        <span>Identification confidence {(tooth.confidence * 100).toFixed(0)}%</span>
      </div>
      <div className="inspection-status">
        <span>Validation</span>
        <strong>{tooth.validationStatus}</strong>
        <p>{tooth.validationMessage}</p>
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
                  disabled={Boolean(draftMovement.locked)}
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
        <strong>{tooth.accumulated ? formatMovement(tooth.accumulated) : formatMovement(tooth.movement)}</strong>
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
            <button className="icon-button" onClick={onUndo} disabled={!canUndo} aria-label="Undo doctor edit">Undo</button>
            <button className="icon-button" onClick={onRedo} disabled={!canRedo} aria-label="Redo doctor edit">Redo</button>
          </div>
          <div className="readonly-note">
            Doctor editing is explicit and read-only until Apply. No clinical correction is
            automatic.
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
