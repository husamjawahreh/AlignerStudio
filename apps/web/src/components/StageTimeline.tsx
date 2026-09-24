import type { ReviewStage } from "../review/types";

interface StageTimelineProps {
  stages: readonly ReviewStage[];
  selectedIndex: number;
  isPlaying: boolean;
  onSelect: (index: number) => void;
  onPrevious: () => void;
  onNext: () => void;
  onTogglePlay: () => void;
}

export function StageTimeline({
  stages,
  selectedIndex,
  isPlaying,
  onSelect,
  onPrevious,
  onNext,
  onTogglePlay,
}: StageTimelineProps): JSX.Element {
  return (
    <section className="timeline-panel" aria-label="Treatment stage timeline">
      <div className="timeline-heading">
        <div>
          <span className="eyebrow">Stage Timeline</span>
          <h2>{stages[selectedIndex]?.label ?? `Stage ${selectedIndex}`}</h2>
        </div>
        <div className="timeline-actions">
          <button
            className="icon-button"
            onClick={onPrevious}
            disabled={selectedIndex === 0}
            aria-label="Previous stage"
          >
            ‹
          </button>
          <button
            className="play-button"
            onClick={onTogglePlay}
            aria-label={isPlaying ? "Pause stages" : "Play stages"}
          >
            {isPlaying ? "Ⅱ" : "▶"}
          </button>
          <button
            className="icon-button"
            onClick={onNext}
            disabled={selectedIndex === stages.length - 1}
            aria-label="Next stage"
          >
            ›
          </button>
        </div>
      </div>
      <input
        className="stage-slider"
        type="range"
        min={0}
        max={Math.max(stages.length - 1, 0)}
        value={selectedIndex}
        onChange={(event) => onSelect(Number(event.target.value))}
        aria-label="Stage selector"
      />
      <div className="stage-markers">
        {stages.map((stage) => (
          <button
            className={`stage-marker ${stage.index === selectedIndex ? "is-selected" : ""}`}
            key={stage.stageId}
            onClick={() => onSelect(stage.index)}
          >
            <span>Stage {stage.index}</span>
            <small>
              {stage.label ?? (stage.index === 0 ? "Original" : stage.index === stages.length - 1 ? "Target" : "Review")}
            </small>
          </button>
        ))}
      </div>
    </section>
  );
}
