import type { ReviewStage } from "../review/types";
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
  onSelectStage: (index: number) => void;
  onTogglePlay: () => void;
  onShowUpper: (value: boolean) => void;
  onShowLower: (value: boolean) => void;
  onShowMovementVectors: (value: boolean) => void;
  onRecalculate: () => void;
}

/** Staging left tools — timeline/sequence/parameters from existing stages only. */
export function StagingPanel({
  stages,
  selectedIndex,
  isPlaying,
  showUpper,
  showLower,
  showMovementVectors,
  treatmentAvailable,
  recalculationState,
  onSelectStage,
  onTogglePlay,
  onShowUpper,
  onShowLower,
  onShowMovementVectors,
  onRecalculate,
}: StagingPanelProps): JSX.Element {
  const sequence = buildStagingSequence(stages);
  const current = stages[selectedIndex] ?? null;
  const goals = buildStageGoals(current);
  const parameters = buildStageParameters(current);
  const toothReview = buildPerToothMovementReview(current?.teeth ?? []);

  return (
    <div className="staging-panel case-form" data-testid="staging-panel">
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
