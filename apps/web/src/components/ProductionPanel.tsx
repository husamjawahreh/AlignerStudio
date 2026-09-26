import type { ReactNode } from "react";
import type { ReviewBundle } from "../review/types";
import { AdvancedDetails, TruthBadge } from "../design-system";
import { formatProductTruthLabel, normalizeProductTruth } from "../design-system/truthState";
import { buildProductionNavigation } from "../workflowNavigationPresentation";

interface ProductionPanelProps {
  bundle: ReviewBundle;
  treatmentAvailable: boolean;
  onExport: () => void;
  onSelectProductionSource?: (stageIndex: number, sourceKind: string) => void;
}

function truthOrLabel(value: string | null | undefined): string {
  return formatProductTruthLabel(value);
}

/** Production left panel — honest readiness by component; no fake manufacturing ready. */
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
    bundle.stages.length > 0 ? bundle.stages[bundle.stages.length - 1]?.index : null;
  const overallTruth =
    normalizeProductTruth(production?.overall_truth_state) ?? "requires_review";

  return (
    <div className="production-panel case-form" data-testid="production-panel">
      <section className="analysis-section" aria-labelledby="production-heading">
        <h3 id="production-heading" className="eyebrow">
          Production
        </h3>
        <p className="cad-review-note" data-testid="production-manufacturing-limit">
          Export is an engineering package. Manufacturing capabilities that are not available stay
          unavailable. This is not manufacturing readiness.
        </p>
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
              <TruthBadge state={overallTruth} />
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Freshness</span>
            <strong data-testid="production-freshness">
              {truthOrLabel(production.freshness)}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Source</span>
            <strong data-testid="production-source-kind">
              {truthOrLabel(production.binding.source_kind)}
              {production.binding.selected_stage_index != null
                ? ` · stage ${production.binding.selected_stage_index}`
                : ""}
            </strong>
          </div>
          {onSelectProductionSource && finalStageIndex != null && (
            <button
              className="secondary-button"
              data-testid="select-final-production-source"
              onClick={() => onSelectProductionSource(finalStageIndex, "final_target")}
              disabled={!treatmentAvailable}
            >
              Select final stage as source
            </button>
          )}
          <AdvancedDetails summary="Technical details">
            <div className="cad-stat-row">
              <span>Version</span>
              <strong data-testid="production-version-id">{production.production_version_id}</strong>
            </div>
            {production.shell_generated ? (
              <small className="cad-review-note">
                Engineering offset sample present — Requires Review; not manufacturing certified.
              </small>
            ) : null}
          </AdvancedDetails>
        </section>
      )}

      {readiness && (
        <section className="analysis-section" aria-labelledby="production-readiness">
          <h3 id="production-readiness" className="eyebrow">
            Capability readiness
          </h3>
          {(
            [
              ["source_treatment_state", "Source state"],
              ["validation_current", "Validation"],
              ["shell", "Shell / offset"],
              ["trimline", "Trimline"],
              ["thickness_defined", "Thickness"],
              ["undercut_analysis", "Undercut"],
              ["mesh_qc", "Mesh QC"],
              ["export_validation", "Export check"],
              ["stage_model_export", "Stage export"],
            ] as const
          ).map(([key, label]) => (
            <div className="cad-stat-row" key={key}>
              <span>{label}</span>
              <strong>{truthOrLabel(readiness[key])}</strong>
            </div>
          ))}
          <small className="cad-review-note">
            Manufacturing certified: no · Clinically approved: no
          </small>
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
        <AdvancedDetails summary="Manufacturing boundary">
          <div className="cad-stat-row">
            <span>Package kind</span>
            <strong>{boundary.packageKind.replaceAll("_", " ")}</strong>
          </div>
          <div className="cad-stat-row">
            <span>Shell generation</span>
            <strong>{boundary.applianceShellGeneration.replaceAll("_", " ")}</strong>
          </div>
          <div className="cad-stat-row">
            <span>Trimline</span>
            <strong>{boundary.trimlineCutline.replaceAll("_", " ")}</strong>
          </div>
        </AdvancedDetails>
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
          Select a production source, review capability readiness, then export. Engineering offset
          remains review-only.
        </p>
      </div>
      {children}
    </>
  );
}
