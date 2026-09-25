import type { ReactNode } from "react";
import type {
  FeedbackModel,
  InspectorModel,
  SegmentationReviewModel,
  ToolItem,
  ToothReviewLabel,
  UnavailableToolNote,
} from "../../interaction/model";

export function SegmentationReviewStrip({
  model,
  patientReference,
}: {
  model: SegmentationReviewModel;
  patientReference: string | null;
}): JSX.Element {
  return (
    <section
      className="segmentation-review-strip"
      data-testid="segmentation-review-strip"
      data-segmentation-kind={model.kind}
      aria-label="Segmentation review"
    >
      <div className="segmentation-review-primary">
        <span className="eyebrow">Segmentation review</span>
        <strong data-testid="analysis-segmentation-state">{model.headline}</strong>
        <p>{model.whatHappened}</p>
      </div>
      <dl className="segmentation-review-facts">
        <div>
          <dt>Case</dt>
          <dd>{patientReference?.trim() || "No case"}</dd>
        </div>
        <div>
          <dt>Upper</dt>
          <dd>{model.upperCountLabel}</dd>
        </div>
        <div>
          <dt>Lower</dt>
          <dd>{model.lowerCountLabel}</dd>
        </div>
        <div>
          <dt>Instances</dt>
          <dd data-testid="analysis-tooth-count">{model.instanceCountLabel}</dd>
        </div>
        <div>
          <dt>Unresolved identity</dt>
          <dd data-testid="unresolved-identity-count">{model.unresolvedIdentityLabel}</dd>
        </div>
        <div>
          <dt>Provenance</dt>
          <dd data-testid="segmentation-provenance">{model.provenanceLabel}</dd>
        </div>
        {model.confidenceLabel ? (
          <div>
            <dt>Confidence</dt>
            <dd>{model.confidenceLabel}</dd>
          </div>
        ) : null}
      </dl>
      <p className="segmentation-review-next">
        <span className="eyebrow">Next</span> {model.nextStep}
      </p>
      <p className="segmentation-review-limit" data-testid="missing-tooth-statement">
        {model.missingToothStatement}
      </p>
      {model.runtimeBlocker ? (
        <p className="segmentation-review-blocker" data-testid="segmentation-runtime-blocker">
          {model.runtimeBlocker}
        </p>
      ) : null}
    </section>
  );
}

export function DentalArchMap({
  entries,
  kind,
  selectedKeys,
  hoveredKey,
  onSelect,
  onHover,
}: {
  entries: readonly ToothReviewLabel[];
  kind: SegmentationReviewModel["kind"];
  selectedKeys: readonly string[];
  hoveredKey: string | null;
  onSelect: (toothRef: string, additive: boolean) => void;
  onHover: (toothRef: string | null) => void;
}): JSX.Element {
  const blocked =
    kind === "blocked_by_environment" || kind === "failed" || kind === "not_available" || kind === "not_run";
  const upper = entries.filter((entry) => entry.arch === "upper");
  const lower = entries.filter((entry) => entry.arch === "lower");
  const other = entries.filter((entry) => entry.arch == null);

  return (
    <div
      className="dental-arch-map"
      data-testid="dental-arch-map"
      data-map-state={blocked ? "unavailable" : entries.length === 0 ? "empty" : "ready"}
      onMouseLeave={() => onHover(null)}
    >
      <span className="eyebrow">Dental map</span>
      {blocked ? (
        <p data-testid="dental-map-unavailable">
          Segmentation is {kind.replaceAll("_", " ")}. This is not zero teeth.
        </p>
      ) : entries.length === 0 ? (
        <p>No persisted tooth instances.</p>
      ) : (
        <>
          <ArchRow
            label="Upper"
            entries={upper}
            selectedKeys={selectedKeys}
            hoveredKey={hoveredKey}
            onSelect={onSelect}
            onHover={onHover}
          />
          <ArchRow
            label="Lower"
            entries={lower}
            selectedKeys={selectedKeys}
            hoveredKey={hoveredKey}
            onSelect={onSelect}
            onHover={onHover}
          />
          {other.length > 0 ? (
            <ArchRow
              label="Arch not set"
              entries={other}
              selectedKeys={selectedKeys}
              hoveredKey={hoveredKey}
              onSelect={onSelect}
              onHover={onHover}
            />
          ) : null}
        </>
      )}
    </div>
  );
}

function ArchRow({
  label,
  entries,
  selectedKeys,
  hoveredKey,
  onSelect,
  onHover,
}: {
  label: string;
  entries: readonly ToothReviewLabel[];
  selectedKeys: readonly string[];
  hoveredKey: string | null;
  onSelect: (toothRef: string, additive: boolean) => void;
  onHover: (toothRef: string | null) => void;
}): JSX.Element {
  return (
    <div className="dental-arch-row">
      <span>{label}</span>
      <div role="listbox" aria-label={`${label} teeth`} aria-multiselectable="true">
        {entries.length === 0 ? <small>None persisted</small> : null}
        {entries.map((entry) => {
          const selected = selectedKeys.includes(entry.toothRef);
          const hovered = hoveredKey === entry.toothRef;
          return (
            <button
              key={entry.toothRef}
              type="button"
              role="option"
              aria-selected={selected}
              className={`dental-map-item${selected ? " is-selected" : ""}${hovered ? " is-hovered" : ""}${entry.unresolved ? " is-unresolved" : ""}`}
              data-testid={`dental-map-${entry.toothRef}`}
              data-tooth-ref={entry.toothRef}
              title={entry.unresolved ? `${entry.toothRef} · identity not resolved` : entry.text}
              onMouseEnter={() => onHover(entry.toothRef)}
              onFocus={() => onHover(entry.toothRef)}
              onClick={(event) => onSelect(entry.toothRef, event.shiftKey || event.metaKey || event.ctrlKey)}
            >
              {entry.text}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function ContextualWorkspaceToolbar({
  tools,
  unavailable,
  selectionCount,
  onTool,
  extra,
}: {
  tools: readonly ToolItem[];
  unavailable: readonly UnavailableToolNote[];
  selectionCount: number;
  onTool: (id: string) => void;
  extra?: ReactNode;
}): JSX.Element {
  return (
    <div className="contextual-workspace-toolbar" data-testid="contextual-toolbar" role="toolbar" aria-label="Viewport tools">
      <span className="toolbar-selection-count" data-testid="selection-count">
        {selectionCount === 0 ? "No selection" : `${selectionCount} selected`}
      </span>
      {tools.map((tool) => (
        <button
          key={tool.id}
          type="button"
          className={tool.active ? "viewer-tool is-active" : "viewer-tool"}
          disabled={!tool.available}
          title={`${tool.reason}${tool.shortcut ? ` Shortcut ${tool.shortcut}.` : ""}`}
          aria-keyshortcuts={tool.shortcut}
          data-testid={`tool-${tool.id}`}
          onClick={() => onTool(tool.id)}
        >
          {tool.label}
        </button>
      ))}
      {extra}
      {unavailable.length > 0 ? (
        <details className="toolbar-unavailable" data-testid="toolbar-unavailable">
          <summary>Unavailable</summary>
          <ul>
            {unavailable.map((note) => (
              <li key={note.id}>
                <strong>{note.label}.</strong> {note.reason}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

export function AdaptiveInspector({
  model,
  minimized,
  onToggle,
}: {
  model: InspectorModel;
  minimized: boolean;
  onToggle: () => void;
}): JSX.Element {
  return (
    <section
      className={`adaptive-inspector${minimized ? " is-minimized" : ""}`}
      data-testid="adaptive-inspector"
      data-inspector-mode={model.mode}
    >
      <header>
        <span className="eyebrow">Inspector</span>
        <button type="button" className="text-button" onClick={onToggle} data-testid="inspector-toggle">
          {minimized ? "Show" : "Hide"}
        </button>
      </header>
      {minimized ? null : (
        <>
          <h2>{model.title}</h2>
          {model.rows.map((row) => (
            <div className="cad-stat-row" key={row.label}>
              <span>{row.label}</span>
              <strong>{row.value}</strong>
            </div>
          ))}
          {model.limitations.length > 0 ? (
            <ul className="inspector-limitations">
              {model.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          {model.advanced.length > 0 ? (
            <details data-testid="inspector-advanced">
              <summary>Advanced details</summary>
              {model.advanced.map((row) => (
                <div className="cad-stat-row" key={row.label}>
                  <span>{row.label}</span>
                  <strong>{row.value}</strong>
                </div>
              ))}
            </details>
          ) : null}
        </>
      )}
    </section>
  );
}

export function PrimaryStatus({ feedback }: { feedback: FeedbackModel }): JSX.Element {
  return (
    <div
      className={`primary-status is-${feedback.state}`}
      data-testid="primary-status"
      data-status-surface="primary"
      data-feedback-state={feedback.state}
    >
      <strong>{feedback.state.replaceAll("_", " ")}</strong>
      <span>{feedback.whatHappened}</span>
      {feedback.elapsedLabel ? <span>{feedback.elapsedLabel}</span> : null}
      {feedback.state === "processing" ? <span>{feedback.remainingNote}</span> : null}
    </div>
  );
}

export function SelectionWidget({
  label,
  count,
}: {
  label: string | null;
  count: number;
}): JSX.Element | null {
  if (count === 0) return null;
  return (
    <div className="smart-widget" data-testid="selection-widget">
      <span className="eyebrow">{count === 1 ? "Selected tooth" : "Selection"}</span>
      <strong>{label ?? `${count} teeth`}</strong>
    </div>
  );
}
