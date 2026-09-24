import type { ReactNode } from "react";

export function InspectorSection({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return <section className="production-inspector-section"><h3>{title}</h3>{children}</section>;
}

export function StatusPill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "success" | "warning" | "danger" }): JSX.Element {
  return <span className={`production-status-pill is-${tone}`}>{children}</span>;
}

export function SuggestionCard({ title, detail, action }: { title: string; detail: string; action?: ReactNode }): JSX.Element {
  return <div className="production-suggestion"><strong>{title}</strong><p>{detail}</p>{action}</div>;
}

export function CaseLoadingOverlay({ stage }: { stage: string }): JSX.Element {
  return <div className="case-loading-overlay" role="status" aria-live="polite"><img src="/assets/AS-logo.png" alt="" /><div><strong>{stage}</strong><span>Preparing your dental workspace</span></div><span className="loading-bar" /></div>;
}

export function ProductionEmptyState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }): JSX.Element {
  return <div className="production-empty-state"><span className="eyebrow">Next step</span><h2>{title}</h2><p>{detail}</p>{action}</div>;
}
