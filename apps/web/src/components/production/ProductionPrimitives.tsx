import type { ReactNode } from "react";
import type { LoadingPresentation } from "./loadingPresentation";
import { formatElapsedLabel } from "./loadingPresentation";

export function InspectorSection({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="production-inspector-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

export function StatusPill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger";
}): JSX.Element {
  return <span className={`production-status-pill is-${tone}`}>{children}</span>;
}

export function SuggestionCard({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}): JSX.Element {
  return (
    <div className="production-suggestion">
      <strong>{title}</strong>
      <p>{detail}</p>
      {action}
    </div>
  );
}

/** Aligner Studio branded loading overlay — renders only truthful presentation data. */
export function CaseLoadingOverlay({
  presentation,
}: {
  presentation: LoadingPresentation;
}): JSX.Element {
  const elapsed = formatElapsedLabel(presentation.elapsedSeconds);
  const determinate = presentation.mode === "determinate" && presentation.progressPercent != null;

  return (
    <div
      className="case-loading-overlay"
      role="status"
      aria-live="polite"
      aria-busy="true"
      data-testid="case-loading-overlay"
      data-loading-source={presentation.source}
      data-loading-mode={presentation.mode}
    >
      <div className="case-loading-card">
        <div className="case-loading-brand">
          <img src="/assets/AS-logo.png" alt="" />
          <div>
            <span className="case-loading-brand-name">{presentation.brand}</span>
            <strong>{presentation.title}</strong>
          </div>
        </div>

        <div className="case-loading-meta">
          <span>{presentation.detail}</span>
          {elapsed ? <span>{elapsed}</span> : null}
          {presentation.currentStageId ? (
            <span className="case-loading-stage-id">{presentation.currentStageId}</span>
          ) : null}
        </div>

        <div
          className={`loading-track is-${presentation.mode}`}
          aria-valuemin={determinate ? 0 : undefined}
          aria-valuemax={determinate ? 100 : undefined}
          aria-valuenow={determinate ? presentation.progressPercent ?? undefined : undefined}
          role={determinate ? "progressbar" : undefined}
        >
          <div
            className="loading-fill"
            style={
              determinate
                ? { width: `${presentation.progressPercent}%` }
                : undefined
            }
          />
        </div>

        {presentation.stages.length > 0 ? (
          <ul className="case-loading-stages" aria-label="Reported processing stages">
            {presentation.stages.map((stage) => (
              <li key={stage.id} className={`is-${stage.state}`} data-stage-id={stage.id}>
                <span className="case-loading-stage-mark" aria-hidden="true" />
                <span>{stage.label}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

export function ProductionEmptyState({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}): JSX.Element {
  return (
    <div className="production-empty-state">
      <span className="eyebrow">Next step</span>
      <h2>{title}</h2>
      <p>{detail}</p>
      {action}
    </div>
  );
}
