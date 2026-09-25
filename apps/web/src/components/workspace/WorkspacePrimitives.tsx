import type { ReactNode } from "react";

// Existing CAD shell primitives — preserved for P0–P8 compatibility.
// FV-01 design-system components live in `apps/web/src/design-system/`.

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps): JSX.Element {
  return <div className="cad-shell as-shell">{children}</div>;
}

interface WorkflowHeaderProps {
  children: ReactNode;
}

export function WorkflowHeader({ children }: WorkflowHeaderProps): JSX.Element {
  return <header className="cad-header as-topbar">{children}</header>;
}

interface PanelProps {
  children: ReactNode;
  className?: string;
}

export function LeftToolPanel({ children, className = "" }: PanelProps): JSX.Element {
  return <aside className={`cad-panel cad-tools as-panel as-panel-left ${className}`}>{children}</aside>;
}

export function RightInspector({ children, className = "" }: PanelProps): JSX.Element {
  return <aside className={`cad-panel cad-inspector as-panel as-panel-right ${className}`}>{children}</aside>;
}

export function BottomTimeline({ children }: PanelProps): JSX.Element {
  return <div className="cad-timeline">{children}</div>;
}

export function WorkspaceContainer({ children, className = "" }: PanelProps): JSX.Element {
  return <main className={`cad-workspace as-workspace ${className}`}>{children}</main>;
}

export function ViewerOverlay({ children }: PanelProps): JSX.Element {
  return <div className="cad-viewer-overlay">{children}</div>;
}

export function StatusBar({ children }: PanelProps): JSX.Element {
  return <div className="cad-statusbar as-statusbar">{children}</div>;
}
