import type { ReviewStage, SmartStagingPayload } from "../review/types";
import { AdvancedDetails } from "../design-system";
import {
  buildPerToothMovementReview,
  buildStageGoals,
  buildStageParameters,
  buildStagingSequence,
} from "../treatmentWorkflowPresentation";

interface StagingPanelProps {
  stages: readonly ReviewStage[];
  selectedIndex: number;
  isPlaying: boolean;
  showUpper: boolean;
  showLower: boolean;
  showMovementVectors: boolean;
  treatmentAvailable: boolean;
  recalculationState: "idle" | "recalculating" | "complete";
  smartStaging?: SmartStagingPayload | null;
  onSelectStage: (index: number) => void;
  onTogglePlay: () => void;
  onShowUpper: (value: boolean) => void;
  onShowLower: (value: boolean) => void;
  onShowMovementVectors: (value: boolean) => void;
  onRecalculate: () => void;
  onRegenerateStaging?: () => void;
  onSaveStagingVersion?: () => void;
}

/** Staging left tools — timeline/sequence/parameters + WP-06 smart staging honesty. */
export function StagingPanel({
  stages,
  selectedIndex,
  isPlaying,
  showUpper,
  showLower,
  showMovementVectors,
  treatmentAvailable,
  recalculationState,
  smartStaging = null,
  onSelectStage,
  onTogglePlay,
  onShowUpper,
  onShowLower,
  onShowMovementVectors,
  onRecalculate,
  onRegenerateStaging,
  onSaveStagingVersion,
}: StagingPanelProps): JSX.Element {
  const sequence = buildStagingSequence(stages);
  const current = stages[selectedIndex] ?? null;
  const goals = buildStageGoals(current);
  const parameters = buildStageParameters(current);
  const toothReview = buildPerToothMovementReview(current?.teeth ?? []);
  const freshness = smartStaging?.meta?.freshness ?? smartStaging?.freshness ?? "unavailable";
  const isStale = freshness === "stale";

  return (
    <div className="staging-panel case-form" data-testid="staging-panel">
      <section className="analysis-section" aria-labelledby="smart-staging" data-testid="smart-staging-status">
        <h3 id="smart-staging" className="eyebrow">
          Smart Staging
        </h3>
        <div className="cad-stat-row">
          <span>Freshness</span>
          <strong data-testid="staging-freshness">{freshness}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Truth state</span>
          <strong>{(smartStaging?.meta?.truth_state ?? "unavailable").replaceAll("_", " ")}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Final equals target</span>
          <strong>
            {smartStaging?.final_equals_target == null
              ? "Unavailable"
              : smartStaging.final_equals_target
                ? "Yes"
                : "No"}
          </strong>
        </div>
        <AdvancedDetails summary="Staging technical details">
          <div className="cad-stat-row">
            <span>Algorithm</span>
            <strong>
              {smartStaging?.meta
                ? `${smartStaging.meta.algorithm_name} @ ${smartStaging.meta.algorithm_version}`
                : "Unavailable"}
            </strong>
          </div>
        </AdvancedDetails>
        <small className="cad-review-note">
          Computational staging proposal — not clinically optimized or approved.
        </small>
        {isStale && (
          <small className="diagnostic-warning" data-testid="staging-stale-warning">
            Staging is stale relative to the current Treatment Setup version. Regenerate explicitly.
          </small>
        )}
        {onRegenerateStaging && (
          <button
            className="primary-button"
            type="button"
            onClick={onRegenerateStaging}
            disabled={!treatmentAvailable || recalculationState === "recalculating"}
            data-testid="staging-regenerate"
          >
            {recalculationState === "recalculating" ? "Regenerating..." : "Generate / Regenerate Staging"}
          </button>
        )}
        {onSaveStagingVersion && (
          <button
            className="secondary-button"
            type="button"
            onClick={onSaveStagingVersion}
            disabled={!treatmentAvailable || isStale}
            data-testid="staging-save-version"
          >
            Save staging version
          </button>
        )}
      </section>

      <section className="analysis-section" aria-labelledby="stage-timeline">
        <h3 id="stage-timeline" className="eyebrow">
          Stage Timeline
        </h3>
        <div className="cad-stat-row">
          <span>Current stage</span>
          <strong>{current ? `${current.index + 1} / ${stages.length}` : "Unavailable"}</strong>
        </div>
        <button className="secondary-button" onClick={onTogglePlay} disabled={!treatmentAvailable}>
          {isPlaying ? "Pause playback" : "Play playback"}
        </button>
      </section>

      <section className="analysis-section" aria-labelledby="movement-sequence">
        <h3 id="movement-sequence" className="eyebrow">
          Movement Sequence
        </h3>
        {sequence.length === 0 ? (
          <small className="cad-review-note">No stages available.</small>
        ) : (
          sequence.map((stage) => (
            <button
              key={stage.stageId}
              className={`text-button staging-sequence-item ${
                stage.index === selectedIndex ? "is-active" : ""
              }`}
              onClick={() => onSelectStage(stage.index)}
            >
              {stage.label} · {stage.role}
            </button>
          ))
        )}
      </section>

      <section className="analysis-section" aria-labelledby="stage-goals">
        <h3 id="stage-goals" className="eyebrow">
          Stage Goals
        </h3>
        <div className="cad-stat-row">
          <span>Goal</span>
          <strong>{goals.label}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Type</span>
          <strong>{goals.type}</strong>
        </div>
        {goals.findings.map((finding) => (
          <small className="diagnostic-warning" key={finding}>
            {finding}
          </small>
        ))}
      </section>

      <section className="analysis-section" aria-labelledby="stage-parameters">
        <h3 id="stage-parameters" className="eyebrow">
          Stage Parameters
        </h3>
        {parameters.map((parameter) => (
          <div className="cad-stat-row" key={parameter.name}>
            <span>{parameter.name}</span>
            <strong>{parameter.value}</strong>
          </div>
        ))}
        <button
          className="primary-button"
          onClick={onRecalculate}
          disabled={!treatmentAvailable || recalculationState === "recalculating"}
        >
          {recalculationState === "recalculating" ? "Recalculating..." : "Dynamic staging refresh"}
        </button>
      </section>

      <section className="analysis-section" aria-labelledby="staging-arch-controls">
        <h3 id="staging-arch-controls" className="eyebrow">
          Upper / Lower controls
        </h3>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showUpper}
            onChange={(event) => onShowUpper(event.target.checked)}
          />
          <span>Upper Arch</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showLower}
            onChange={(event) => onShowLower(event.target.checked)}
          />
          <span>Lower Arch</span>
        </label>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showMovementVectors}
            disabled={!treatmentAvailable}
            onChange={(event) => onShowMovementVectors(event.target.checked)}
          />
          <span>Tooth Movement</span>
        </label>
      </section>

      <section className="analysis-section" aria-labelledby="per-tooth-review">
        <h3 id="per-tooth-review" className="eyebrow">
          Per-tooth movement review
        </h3>
        {toothReview.length === 0 ? (
          <small className="cad-review-note">No tooth movement rows for this stage.</small>
        ) : (
          toothReview.map((row) => (
            <div className="cad-stat-row" key={`${row.label}-${row.arch}`}>
              <span>
                {row.label} · {row.arch}
              </span>
              <strong>{row.translation.toFixed(3)}</strong>
            </div>
          ))
        )}
      </section>
    </div>
  );
}

interface StagingInspectorProps {
  stage: ReviewStage | null;
  stageCount: number;
  isPlaying: boolean;
}

export function StagingInspector({
  stage,
  stageCount,
  isPlaying,
}: StagingInspectorProps): JSX.Element {
  const goals = buildStageGoals(stage);
  return (
    <div className="cad-inspector-section" data-testid="staging-inspector">
      <span className="eyebrow">Staging</span>
      <h2>Stage Timeline</h2>
      <div className="cad-stat-row">
        <span>Current / total</span>
        <strong>
          {stage ? `${stage.index + 1} / ${stageCount}` : "Unavailable"}
        </strong>
      </div>
      <div className="cad-stat-row">
        <span>Playback</span>
        <strong>{isPlaying ? "Playing" : "Paused"}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Stage Goals</span>
        <strong>{goals.label}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Original / current / target</span>
        <strong>
          {stageCount > 0 ? `0 · ${stage?.index ?? "—"} · ${Math.max(stageCount - 1, 0)}` : "Unavailable"}
        </strong>
      </div>
    </div>
  );
}
