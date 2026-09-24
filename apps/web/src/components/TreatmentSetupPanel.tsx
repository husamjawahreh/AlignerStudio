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
  onSelectAlternative?: (alternativeId: string) => void;
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
  onSelectAlternative,
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

      {bundle.planningIntelligence && (
        <section className="analysis-section" aria-labelledby="planning-intelligence">
          <h3 id="planning-intelligence" className="eyebrow">
            Planning Intelligence
          </h3>
          <small className="cad-review-note">{bundle.planningIntelligence.rule}</small>
          <div className="cad-stat-row">
            <span>Landmark-assisted</span>
            <strong>
              {bundle.planningIntelligence.landmarkAssistedTargetSetup.replaceAll("_", " ")}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Arch-form-aware</span>
            <strong>
              {bundle.planningIntelligence.archFormAwarePlanning.replaceAll("_", " ")}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Occlusion-aware</span>
            <strong>
              {bundle.planningIntelligence.occlusionAwarePlanning.replaceAll("_", " ")}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Collision-aware</span>
            <strong>
              {bundle.planningIntelligence.collisionAwareCandidateGeneration.replaceAll(
                "_",
                " ",
              )}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Constrained 6-DOF</span>
            <strong>
              {bundle.planningIntelligence.constrainedSixDofTrajectories.replaceAll("_", " ")}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Staging proposals</span>
            <strong>
              {bundle.planningIntelligence.stagingProposals.replaceAll("_", " ")}
            </strong>
          </div>
          {bundle.planningIntelligence.alternatives.map((alternative) => (
            <div className="proposal-row" key={alternative.alternativeId}>
              <div className="proposal-row-header">
                <strong>{alternative.label}</strong>
                <span className={`proposal-status ${alternative.isActive ? "accepted" : ""}`}>
                  {alternative.isActive ? "active" : alternative.contract.decisionState.replaceAll("_", " ")}
                </span>
              </div>
              <div className="proposal-values">
                <span>Model {alternative.contract.modelName}</span>
                <span>v{alternative.contract.modelVersion}</span>
                <span>
                  Confidence{" "}
                  {alternative.contract.confidence === null
                    ? "not provided"
                    : alternative.contract.confidence}
                </span>
                <span>Validation {alternative.contract.deterministicValidationStatus}</span>
                <span>
                  Collisions {alternative.collisionCount} · Stages {alternative.stageCount}
                </span>
              </div>
              {onSelectAlternative &&
                !alternative.isActive &&
                alternative.contract.decisionState !== "rejected_by_validation" && (
                  <div className="proposal-actions">
                    <button
                      className="text-button"
                      onClick={() => onSelectAlternative(alternative.alternativeId)}
                    >
                      Accept setup
                    </button>
                  </div>
                )}
            </div>
          ))}
          {bundle.planningIntelligence.researchAdapters.map((adapter) => (
            <div className="cad-stat-row" key={adapter.adapterId}>
              <span>{adapter.modelName}</span>
              <strong>{adapter.status.replaceAll("_", " ")}</strong>
            </div>
          ))}
        </section>
      )}
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
