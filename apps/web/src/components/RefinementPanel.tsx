import type { ReactNode } from "react";
import type { ReviewBundle } from "../review/types";
import { buildRefinementNavigation } from "../workflowNavigationPresentation";

type GizmoMode = "translate" | "rotate";

interface RefinementPanelProps {
  bundle: ReviewBundle;
  gizmoMode: GizmoMode;
  treatmentAvailable: boolean;
  onGizmoMode: (mode: GizmoMode) => void;
}

/** Refinement left navigation — Master Plan labels; existing controls only. */
export function RefinementPanel({
  bundle,
  gizmoMode,
  treatmentAvailable,
  onGizmoMode,
}: RefinementPanelProps): JSX.Element {
  const rows = buildRefinementNavigation(bundle);

  return (
    <div className="refinement-panel case-form" data-testid="refinement-panel">
      <section className="analysis-section" aria-labelledby="refinement-heading">
        <h3 id="refinement-heading" className="eyebrow">
          Refinement
        </h3>
        <small className="cad-review-note">
          Tooth Controls, Movement, Attachments, IPR, and Edit History use live proposal state. Apply
          commits doctor edits through staging rebuild and validation refresh.
        </small>
      </section>

      <section className="analysis-section" aria-labelledby="tooth-controls">
        <h3 id="tooth-controls" className="eyebrow">
          Tooth Controls
        </h3>
        <div className="edit-actions">
          <button
            className={gizmoMode === "translate" ? "primary-button" : "secondary-button"}
            onClick={() => onGizmoMode("translate")}
            disabled={!treatmentAvailable}
          >
            Movement
          </button>
          <button
            className={gizmoMode === "rotate" ? "primary-button" : "secondary-button"}
            onClick={() => onGizmoMode("rotate")}
            disabled={!treatmentAvailable}
          >
            Rotate
          </button>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="movement-nav">
        <h3 id="movement-nav" className="eyebrow">
          Movement
        </h3>
        <div className="cad-stat-row">
          <span>Status</span>
          <strong>{rows.find((row) => row.id === "movement")?.value ?? "Unavailable"}</strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="attachments-nav">
        <h3 id="attachments-nav" className="eyebrow">
          Attachments
        </h3>
        <div className="cad-stat-row">
          <span>Sites</span>
          <strong>{rows.find((row) => row.id === "attachments")?.value ?? "0"}</strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="ipr-nav">
        <h3 id="ipr-nav" className="eyebrow">
          IPR
        </h3>
        <div className="cad-stat-row">
          <span>Sites</span>
          <strong>{rows.find((row) => row.id === "ipr")?.value ?? "0"}</strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="edit-history-nav">
        <h3 id="edit-history-nav" className="eyebrow">
          Edit History
        </h3>
        <div className="cad-stat-row">
          <span>Edits</span>
          <strong>{rows.find((row) => row.id === "edit-history")?.value ?? "0"}</strong>
        </div>
      </section>
    </div>
  );
}

interface RefinementInspectorProps {
  editCount: number;
  children?: ReactNode;
}

export function RefinementInspector({
  editCount,
  children,
}: RefinementInspectorProps): JSX.Element {
  return (
    <>
      <div className="cad-inspector-section" data-testid="refinement-inspector">
        <span className="eyebrow">Refinement</span>
        <h2>Tooth Controls</h2>
        <div className="cad-stat-row">
          <span>Edit History</span>
          <strong>{editCount}</strong>
        </div>
      </div>
      {children}
    </>
  );
}
