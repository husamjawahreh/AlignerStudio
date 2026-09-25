import type { ReactNode } from "react";
import type { ReviewBundle } from "../review/types";
import { buildProductionNavigation } from "../workflowNavigationPresentation";

interface ProductionPanelProps {
  bundle: ReviewBundle;
  treatmentAvailable: boolean;
  onExport: () => void;
  onSelectProductionSource?: (stageIndex: number, sourceKind: string) => void;
}

function formatState(value: string | null | undefined): string {
  if (!value) return "Not Available";
  return value.replaceAll("_", " ");
}

/** Production left navigation — honest manufacturing boundary + WP-10 Production CAD. */
export function ProductionPanel({
  bundle,
  treatmentAvailable,
  onExport,
  onSelectProductionSource,
}: ProductionPanelProps): JSX.Element {
  const rows = buildProductionNavigation(bundle);
  const boundary = bundle.manufacturingBoundary;
  const production = bundle.productionCad;
  const readiness = production?.readiness;
  const finalStageIndex =
    bundle.stages.length > 0 ? bundle.stages[bundle.stages.length - 1]?.stageIndex : null;

  return (
    <div className="production-panel case-form" data-testid="production-panel">
      <section className="analysis-section" aria-labelledby="production-heading">
        <h3 id="production-heading" className="eyebrow">
          Production CAD
        </h3>
        <small className="cad-review-note">
          Treatment design and geometric validation are separated from manufacturing preparation.
          Appliance shells are not generated. CAD export is not manufacturing certification.
        </small>
      </section>

      {production && (
        <section
          className="analysis-section"
          aria-labelledby="production-plan"
          data-testid="production-cad-plan"
        >
          <h3 id="production-plan" className="eyebrow">
            Production Plan
          </h3>
          <div className="cad-stat-row">
            <span>Truth</span>
            <strong data-testid="production-truth">
              {formatState(production.overall_truth_state)}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Freshness</span>
            <strong data-testid="production-freshness">{formatState(production.freshness)}</strong>
          </div>
          <div className="cad-stat-row">
            <span>Source</span>
            <strong data-testid="production-source-kind">
              {formatState(production.binding.source_kind)}
              {production.binding.selected_stage_index != null
                ? ` · stage ${production.binding.selected_stage_index}`
                : ""}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Version</span>
            <strong data-testid="production-version-id">{production.production_version_id}</strong>
          </div>
          {onSelectProductionSource && finalStageIndex != null && (
            <button
              className="secondary-button"
              data-testid="select-final-production-source"
              onClick={() => onSelectProductionSource(finalStageIndex, "final_target")}
              disabled={!treatmentAvailable}
            >
              Select final stage as production source
            </button>
          )}
        </section>
      )}

      {readiness && (
        <section className="analysis-section" aria-labelledby="production-readiness">
          <h3 id="production-readiness" className="eyebrow">
            Manufacturing readiness
          </h3>
          {(
            [
              ["source_treatment_state", "Source state"],
              ["validation_current", "Validation current"],
              ["shell", "Shell"],
              ["trimline", "Trimline"],
              ["thickness_defined", "Thickness"],
              ["undercut_analysis", "Undercut"],
              ["mesh_qc", "Mesh QC"],
              ["export_validation", "Export validation"],
              ["stage_model_export", "Stage model export"],
            ] as const
          ).map(([key, label]) => (
            <div className="cad-stat-row" key={key}>
              <span>{label}</span>
              <strong>{formatState(readiness[key])}</strong>
            </div>
          ))}
          <small className="cad-review-note">
            manufacturing_ready={String(readiness.manufacturing_ready)} · certified=
            {String(readiness.manufacturing_certified)}
          </small>
        </section>
      )}

      {production?.qc_checks && production.qc_checks.length > 0 && (
        <section className="analysis-section" aria-labelledby="production-qc">
          <h3 id="production-qc" className="eyebrow">
            Production QC
          </h3>
          {production.qc_checks.slice(0, 10).map((check) => (
            <div className="cad-stat-row" key={check.check_id}>
              <span>{check.label}</span>
              <strong>{formatState(check.status)}</strong>
            </div>
          ))}
        </section>
      )}

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
          models are treatment geometry only. Export is not manufacturing certification.
        </p>
      </div>
      {children}
    </>
  );
}
