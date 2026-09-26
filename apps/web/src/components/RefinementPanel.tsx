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

/** Refinement left nav — concise status; gizmo lives in the contextual viewport toolbar. */
export function RefinementPanel({
  bundle,
  gizmoMode,
  treatmentAvailable,
  onGizmoMode,
}: RefinementPanelProps): JSX.Element {
  const rows = buildRefinementNavigation(bundle);
  const tools = bundle.clinicalTools;
  const attachmentRow = rows.find((row) => row.id === "attachments");
  const iprRow = rows.find((row) => row.id === "ipr");

  return (
    <div className="refinement-panel case-form" data-testid="refinement-panel">
      <section className="analysis-section" aria-labelledby="refinement-heading">
        <h3 id="refinement-heading" className="eyebrow">
          Refinement
        </h3>
        <p className="cad-review-note">
          Select a tooth in the viewport. Move, rotate, lock, exclude, reset, undo, and redo use the stored plan.
        </p>
        {!treatmentAvailable ? (
          <p className="cad-review-note" data-testid="refinement-empty">
            No treatment plan yet. Refinement edits a stored plan and does not create one.
          </p>
        ) : null}
        <ul className="workflow-unsupported" data-testid="refinement-unavailable">
          <li>Boundary edit is not available</li>
          <li>Split is not available</li>
          <li>Merge is not available</li>
          <li>Identity correction is not available</li>
          <li>Measure is not available</li>
          {tools?.readiness?.ipr_measurement === "not_available" || !tools ? (
            <li>IPR is not available</li>
          ) : null}
        </ul>
        {tools?.freshness === "stale" && (
          <p className="proposal-warning" data-testid="clinical-tools-stale">
            Clinical tools need refresh relative to the current setup or staging version.
          </p>
        )}
      </section>

      <section className="analysis-section" aria-labelledby="tooth-controls">
        <h3 id="tooth-controls" className="eyebrow">
          Mode
        </h3>
        <div className="edit-actions">
          <button
            className={gizmoMode === "translate" ? "primary-button" : "secondary-button"}
            onClick={() => onGizmoMode("translate")}
            disabled={!treatmentAvailable}
          >
            Move
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

      <section className="analysis-section" aria-labelledby="attachments-nav">
        <h3 id="attachments-nav" className="eyebrow">
          Attachments
        </h3>
        <div className="cad-stat-row">
          <span>State</span>
          <strong>{attachmentTruthLabel(attachmentRow?.value, tools)}</strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="ipr-nav">
        <h3 id="ipr-nav" className="eyebrow">
          IPR
        </h3>
        <div className="cad-stat-row">
          <span>State</span>
          <strong>{iprTruthLabel(iprRow?.value, tools)}</strong>
        </div>
      </section>
    </div>
  );
}

function attachmentTruthLabel(
  navValue: string | undefined,
  tools: ReviewBundle["clinicalTools"],
): string {
  if (!tools) return "Not Available";
  const sites = tools.readiness?.attachment_placement;
  if (sites === "not_available" || sites === "unavailable") return "Not Available";
  if (sites === "requires_review") return "Requires Review";
  if (navValue === "0" || navValue?.toLowerCase() === "none") return "Requires Review";
  return navValue ?? "Requires Review";
}

function iprTruthLabel(
  navValue: string | undefined,
  tools: ReviewBundle["clinicalTools"],
): string {
  if (!tools) return "Not Available";
  const sites = tools.readiness?.ipr_measurement;
  if (sites === "not_available" || sites === "unavailable") return "Not Available";
  if (sites === "requires_review") return "Requires Review";
  return navValue ?? "Requires Review";
}

interface RefinementInspectorProps {
  children?: ReactNode;
  editCount?: number;
}

export function RefinementInspector({ children, editCount }: RefinementInspectorProps): JSX.Element {
  return (
    <>
      <div className="cad-inspector-section" data-testid="refinement-inspector">
        <span className="eyebrow">Refinement</span>
        <h2>Tooth Controls</h2>
        <p>Adjust the selected tooth, then Apply. Undo and redo are available in the inspector.</p>
        {typeof editCount === "number" ? (
          <div className="cad-stat-row">
            <span>Doctor edits</span>
            <strong>{editCount}</strong>
          </div>
        ) : null}
      </div>
      {children}
    </>
  );
}
