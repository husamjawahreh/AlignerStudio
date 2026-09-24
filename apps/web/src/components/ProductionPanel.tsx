import type { ReactNode } from "react";
import type { ReviewBundle } from "../review/types";
import { buildProductionNavigation } from "../workflowNavigationPresentation";

interface ProductionPanelProps {
  bundle: ReviewBundle;
  treatmentAvailable: boolean;
  onExport: () => void;
}

/** Production left navigation — honest manufacturing boundary from existing bundle only. */
export function ProductionPanel({
  bundle,
  treatmentAvailable,
  onExport,
}: ProductionPanelProps): JSX.Element {
  const rows = buildProductionNavigation(bundle);
  const boundary = bundle.manufacturingBoundary;

  return (
    <div className="production-panel case-form" data-testid="production-panel">
      <section className="analysis-section" aria-labelledby="production-heading">
        <h3 id="production-heading" className="eyebrow">
          Production
        </h3>
        <small className="cad-review-note">
          Treatment design and geometric validation are separated from manufacturing preparation.
          Appliance shells are not generated.
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

      {boundary && (
        <section className="analysis-section" aria-labelledby="manufacturing-boundary">
          <h3 id="manufacturing-boundary" className="eyebrow">
            Manufacturing Boundary
          </h3>
          <div className="cad-stat-row">
            <span>Package kind</span>
            <strong>{boundary.packageKind.replaceAll("_", " ")}</strong>
          </div>
          <div className="cad-stat-row">
            <span>Shell generation</span>
            <strong>{boundary.applianceShellGeneration.replaceAll("_", " ")}</strong>
          </div>
          <div className="cad-stat-row">
            <span>Trimline / cutline</span>
            <strong>{boundary.trimlineCutline.replaceAll("_", " ")}</strong>
          </div>
          <div className="cad-stat-row">
            <span>Separated layers</span>
            <strong>{boundary.treatmentVsManufacturingSeparated ? "yes" : "no"}</strong>
          </div>
          {boundary.notes.slice(0, 2).map((note) => (
            <small className="cad-review-note" key={note}>
              {note}
            </small>
          ))}
        </section>
      )}
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
        <p>
          Manufacturing Preparation remains Unavailable until appliance tooling exists. Stage
          models are treatment geometry only.
        </p>
      </div>
      {children}
    </>
  );
}
