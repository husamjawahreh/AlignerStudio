interface ContextualToothToolbarProps {
  label: string;
  arch: string | null;
  gizmoMode: "translate" | "rotate";
  onGizmoMode: (mode: "translate" | "rotate") => void;
  canEdit: boolean;
  /** Geometric transform allowed — false when locked/excluded. */
  canTransform?: boolean;
  isDirty: boolean;
  locked: boolean;
  excluded: boolean;
  showTargetGhost: boolean;
  targetGhostAvailable: boolean;
  showMovementVectors: boolean;
  onToggleTargetGhost: () => void;
  onToggleMovementVectors: () => void;
  onToggleLocked: () => void;
  onToggleExcluded: () => void;
  onApply: () => void;
  onCancel: () => void;
  onClearSelection: () => void;
  embedded?: boolean;
  /** Lock, exclude, apply, and cancel stay on the numeric inspector. */
  commitOwnedByInspector?: boolean;
}

/** Selection-scoped viewport toolbar wired to live App state (not mock UI). */
export function ContextualToothToolbar({
  label,
  arch,
  gizmoMode,
  onGizmoMode,
  canEdit,
  canTransform = true,
  isDirty,
  locked,
  excluded,
  showTargetGhost,
  targetGhostAvailable,
  showMovementVectors,
  onToggleTargetGhost,
  onToggleMovementVectors,
  onToggleLocked,
  onToggleExcluded,
  onApply,
  onCancel,
  onClearSelection,
  embedded = false,
  commitOwnedByInspector = false,
}: ContextualToothToolbarProps): JSX.Element {
  return (
    <div
      className={embedded ? "contextual-tooth-toolbar is-embedded" : "contextual-tooth-toolbar"}
      aria-label="Selected tooth controls"
      data-testid="contextual-tooth-toolbar"
    >
      <div className="contextual-tooth-meta">
        <strong>{label}</strong>
        {arch ? <span className="contextual-tooth-arch">{arch}</span> : null}
      </div>
      <div className="contextual-tooth-actions">
        <button
          type="button"
          className={gizmoMode === "translate" ? "viewer-tool is-active" : "viewer-tool"}
          onClick={() => onGizmoMode("translate")}
          disabled={!canEdit || !canTransform}
          title="Translate gizmo"
        >
          Move
        </button>
        <button
          type="button"
          className={gizmoMode === "rotate" ? "viewer-tool is-active" : "viewer-tool"}
          onClick={() => onGizmoMode("rotate")}
          disabled={!canEdit || !canTransform}
          title="Rotate gizmo"
        >
          Rotate
        </button>
        <button
          type="button"
          className={showTargetGhost ? "viewer-tool is-active" : "viewer-tool"}
          onClick={onToggleTargetGhost}
          disabled={!targetGhostAvailable}
          title="Toggle target ghost overlay"
        >
          Target
        </button>
        <button
          type="button"
          className={showMovementVectors ? "viewer-tool is-active" : "viewer-tool"}
          onClick={onToggleMovementVectors}
          title="Toggle Tooth Movement overlay"
        >
          Movement
        </button>
        {commitOwnedByInspector ? null : (
          <>
            <button
              type="button"
              className={locked ? "viewer-tool is-active" : "viewer-tool"}
              onClick={onToggleLocked}
              disabled={!canEdit}
              title="Lock tooth"
            >
              {locked ? "Locked" : "Lock"}
            </button>
            <button
              type="button"
              className={excluded ? "viewer-tool is-active" : "viewer-tool"}
              onClick={onToggleExcluded}
              disabled={!canEdit}
              title="Exclude tooth"
            >
              {excluded ? "Excluded" : "Exclude"}
            </button>
            <button
              type="button"
              className="viewer-tool"
              onClick={onApply}
              disabled={!canEdit || !isDirty}
              title="Apply edit"
            >
              Apply
            </button>
            <button
              type="button"
              className="viewer-tool"
              onClick={onCancel}
              disabled={!canEdit || !isDirty}
              title="Cancel edit"
            >
              Cancel
            </button>
          </>
        )}
        <button type="button" className="viewer-tool" onClick={onClearSelection} title="Clear selection">
          Clear
        </button>
      </div>
    </div>
  );
}
