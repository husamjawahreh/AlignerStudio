import type { ReactNode } from "react";
import type { ReviewBundle, ReviewStage } from "../review/types";
import { buildValidationNavigation } from "../workflowNavigationPresentation";

interface ValidationWorkflowPanelProps {
  bundle: ReviewBundle;
  stage: ReviewStage | null;
}

/** Validation left navigation — Master Plan checks from existing summary/stage only. */
export function ValidationWorkflowPanel({
  bundle,
  stage,
}: ValidationWorkflowPanelProps): JSX.Element {
  const rows = buildValidationNavigation(bundle, stage);

  return (
    <div className="validation-workflow-panel case-form" data-testid="validation-workflow-panel">
      <section className="analysis-section" aria-labelledby="validation-heading">
        <h3 id="validation-heading" className="eyebrow">
          Validation
        </h3>
        <small className="cad-review-note">
          Geometry findings only. No clinical approval workflow is represented.
        </small>
        <p className="cad-review-note" data-testid="validation-review-note">
          {bundle.validationCapability
            ? "A validation run is stored. Unavailable checks are not a pass, and this is not a clinical approval."
            : "No validation run for this treatment version. A missing check is not a pass."}
        </p>
      </section>

      {rows.map((row) => (
        <section className="analysis-section" aria-labelledby={`validation-${row.id}`} key={row.id}>
          <h3 id={`validation-${row.id}`} className="eyebrow">
            {row.label}
          </h3>
          <div className="cad-stat-row">
            <span>Status</span>
            <strong>{row.value}</strong>
          </div>
        </section>
      ))}
    </div>
  );
}

interface ValidationWorkflowInspectorProps {
  children?: ReactNode;
  hasStage: boolean;
}

export function ValidationWorkflowInspector({
  children,
  hasStage,
}: ValidationWorkflowInspectorProps): JSX.Element {
  return (
    <>
      <div className="cad-inspector-section" data-testid="validation-workflow-inspector">
        <span className="eyebrow">Validation</span>
        <h2>Review Status</h2>
        {!hasStage && <p>Run analysis before reviewing geometry findings.</p>}
      </div>
      {children}
    </>
  );
}
