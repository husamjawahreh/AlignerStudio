import type { ReactNode } from "react";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps): JSX.Element {
  return <div className="cad-shell">{children}</div>;
}

interface WorkflowHeaderProps {
  children: ReactNode;
}

export function WorkflowHeader({ children }: WorkflowHeaderProps): JSX.Element {
  return <header className="cad-header">{children}</header>;
}

interface PanelProps {
  children: ReactNode;
  className?: string;
}

export function LeftToolPanel({ children, className = "" }: PanelProps): JSX.Element {
  return <aside className={`cad-panel cad-tools ${className}`}>{children}</aside>;
}

export function RightInspector({ children, className = "" }: PanelProps): JSX.Element {
  return <aside className={`cad-panel cad-inspector ${className}`}>{children}</aside>;
}

export function BottomTimeline({ children }: PanelProps): JSX.Element {
  return <div className="cad-timeline">{children}</div>;
}

export function WorkspaceContainer({ children }: PanelProps): JSX.Element {
  return <main className="cad-workspace">{children}</main>;
}

export function ViewerOverlay({ children }: PanelProps): JSX.Element {
  return <div className="cad-viewer-overlay">{children}</div>;
}

export function StatusBar({ children }: PanelProps): JSX.Element {
  return <div className="cad-statusbar">{children}</div>;
}
