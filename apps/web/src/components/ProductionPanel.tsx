import type { ReactNode } from "react";
import type { ReviewBundle } from "../review/types";
import { buildProductionNavigation } from "../workflowNavigationPresentation";

interface ProductionPanelProps {
  bundle: ReviewBundle;
  treatmentAvailable: boolean;
  onExport: () => void;
}

/** Production left navigation — Master Plan package areas from existing bundle only. */
export function ProductionPanel({
  bundle,
  treatmentAvailable,
  onExport,
}: ProductionPanelProps): JSX.Element {
  const rows = buildProductionNavigation(bundle);

  return (
    <div className="production-panel case-form" data-testid="production-panel">
      <section className="analysis-section" aria-labelledby="production-heading">
        <h3 id="production-heading" className="eyebrow">
          Production
        </h3>
        <small className="cad-review-note">
          Navigates existing export package fields. Manufacturing tooling is not implemented here.
        </small>
      </section>

      {rows.map((row) => (
        <section className="analysis-section" aria-labelledby={`production-${row.id}`} key={row.id}>
          <h3 id={`production-${row.id}`} className="eyebrow">
            {row.label}
          </h3>
          <div className="cad-stat-row">
            <span>Status</span>
            <strong>{row.value}</strong>
          </div>
          {row.id === "export-package" && (
            <button
              className="primary-button"
              onClick={onExport}
              disabled={!treatmentAvailable}
            >
              Export Package
            </button>
          )}
        </section>
      ))}
    </div>
  );
}

interface ProductionInspectorProps {
  children?: ReactNode;
}

export function ProductionInspector({ children }: ProductionInspectorProps): JSX.Element {
  return (
    <>
      <div className="cad-inspector-section" data-testid="production-inspector">
        <span className="eyebrow">Production</span>
        <h2>Export Package</h2>
        <p>Manufacturing Preparation and Production QA use the existing export package.</p>
      </div>
      {children}
    </>
  );
}
