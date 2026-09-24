import type { ReactNode } from "react";
import type { ReviewBundle } from "../review/types";
import {
  buildSetupComparison,
  buildTreatmentSetupSummary,
} from "../treatmentWorkflowPresentation";

interface TreatmentSetupPanelProps {
  bundle: ReviewBundle;
  bothArchesValid: boolean;
  backendTreatment: boolean;
  showOriginal: boolean;
  showTargetGhost: boolean;
  originalOpacity: number;
  treatmentAvailable: boolean;
  onGeneratePlan: () => void;
  onToggleInitialPosition: (visible: boolean) => void;
  onToggleTargetPosition: (visible: boolean) => void;
  onOriginalOpacityChange: (value: number) => void;
}

/** Treatment Setup left tools — existing proposal/stage data only. */
export function TreatmentSetupPanel({
  bundle,
  bothArchesValid,
  backendTreatment,
  showOriginal,
  showTargetGhost,
  originalOpacity,
  treatmentAvailable,
  onGeneratePlan,
  onToggleInitialPosition,
  onToggleTargetPosition,
  onOriginalOpacityChange,
}: TreatmentSetupPanelProps): JSX.Element {
  const summary = buildTreatmentSetupSummary(bundle);
  const comparison = buildSetupComparison(bundle.stages[0], bundle.stages.at(-1));

  return (
    <div className="treatment-setup-panel case-form" data-testid="treatment-setup-panel">
      <section className="analysis-section" aria-labelledby="treatment-setup-heading">
        <h3 id="treatment-setup-heading" className="eyebrow">
          Treatment Setup
        </h3>
        <button
          aria-label="Generate Treatment Setup"
          className="primary-button"
          onClick={onGeneratePlan}
          disabled={!bothArchesValid || backendTreatment}
        >
          Review Treatment Setup
        </button>
        <div className="cad-stat-row">
          <span>Target setup</span>
          <strong>{summary.available ? "Available" : "Unavailable"}</strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="initial-position">
        <h3 id="initial-position" className="eyebrow">
          Initial Position
        </h3>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showOriginal}
            onChange={(event) => onToggleInitialPosition(event.target.checked)}
          />
          <span>Show Initial Position</span>
        </label>
        {showOriginal && (
          <label className="range-row">
            <span>Opacity</span>
            <input
              type="range"
              min="0.08"
              max="0.75"
              step="0.01"
              value={originalOpacity}
              onChange={(event) => onOriginalOpacityChange(Number(event.target.value))}
            />
          </label>
        )}
        <div className="cad-stat-row">
          <span>Stage</span>
          <strong>{summary.initialStageLabel}</strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="target-position">
        <h3 id="target-position" className="eyebrow">
          Target Position
        </h3>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showTargetGhost}
            disabled={!treatmentAvailable}
            onChange={(event) => onToggleTargetPosition(event.target.checked)}
          />
          <span>Show Target Position</span>
        </label>
        <div className="cad-stat-row">
          <span>Stage</span>
          <strong>{summary.targetStageLabel}</strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="tooth-movement">
        <h3 id="tooth-movement" className="eyebrow">
          Tooth Movement
        </h3>
        <div className="cad-stat-row">
          <span>Moved teeth</span>
          <strong>
            {summary.movedToothCount === null ? "Unavailable" : summary.movedToothCount}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Total movement</span>
          <strong>
            {summary.totalMovement === null ? "Unavailable" : summary.totalMovement.toFixed(3)}
          </strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="setup-comparison">
        <h3 id="setup-comparison" className="eyebrow">
          Setup Comparison
        </h3>
        <small className="cad-review-note">Original vs target from staged poses (display only).</small>
        {comparison.length === 0 ? (
          <small className="cad-review-note">No comparable movement rows yet.</small>
        ) : (
          comparison.map((row) => (
            <div className="cad-stat-row" key={row.toothKey}>
              <span>
                {row.label} · {row.arch}
              </span>
              <strong>{row.targetMovement.toFixed(3)}</strong>
            </div>
          ))
        )}
      </section>

      <section className="analysis-section" aria-labelledby="plan-versions">
        <h3 id="plan-versions" className="eyebrow">
          Plan versions
        </h3>
        <div className="cad-stat-row">
          <span>Version</span>
          <strong>{summary.planVersionLabel}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Setup alternatives</span>
          <strong>{summary.setupAlternativesLabel}</strong>
        </div>
      </section>
    </div>
  );
}

interface TreatmentSetupInspectorProps {
  bundle: ReviewBundle;
  treatmentAvailable: boolean;
  children?: ReactNode;
}

export function TreatmentSetupInspector({
  bundle,
  treatmentAvailable,
  children,
}: TreatmentSetupInspectorProps): JSX.Element {
  const summary = buildTreatmentSetupSummary(bundle);
  return (
    <>
      <div className="cad-inspector-section" data-testid="treatment-setup-inspector">
        <span className="eyebrow">Treatment Setup</span>
        <h2>{treatmentAvailable ? "Target Position ready" : "Setup unavailable"}</h2>
        <p>
          {treatmentAvailable
            ? "Treatment Setup ready for doctor review."
            : "Run analysis and generate a Treatment Setup."}
        </p>
        <div className="cad-stat-row">
          <span>Tooth Movement</span>
          <strong>
            {summary.movedToothCount === null ? "Unavailable" : summary.movedToothCount}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Total movement</span>
          <strong>
            {summary.totalMovement === null ? "Unavailable" : summary.totalMovement.toFixed(3)}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Plan versions</span>
          <strong>{summary.proposalKind}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Setup alternatives</span>
          <strong>{summary.setupAlternativesLabel}</strong>
        </div>
        {summary.source && (
          <small className="cad-review-note">
            Source: {summary.source}
            {summary.doctorReviewRequired ? " · doctor review required" : ""}
          </small>
        )}
        {summary.warnings.map((warning) => (
          <small className="diagnostic-warning" key={warning}>
            {warning}
          </small>
        ))}
      </div>
      {children}
    </>
  );
}
