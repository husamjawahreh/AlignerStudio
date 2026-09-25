import type { ReactNode } from "react";

interface AppShellProps {
  children: ReactNode;
}

export function DesignAppShell({ children }: AppShellProps): JSX.Element {
  return <div className="as-shell cad-shell">{children}</div>;
}

interface TopBarProps {
  brand: string;
  children?: ReactNode;
  actions?: ReactNode;
}

export function TopBar({ brand, children, actions }: TopBarProps): JSX.Element {
  return (
    <header className="as-topbar cad-header">
      <div className="as-topbar-brand">
        <strong>{brand}</strong>
      </div>
      <div className="as-topbar-center">{children}</div>
      <div className="as-topbar-actions">{actions}</div>
    </header>
  );
}

interface PanelProps {
  children: ReactNode;
  className?: string;
  title?: string;
}

export function LeftInspector({ children, className = "", title }: PanelProps): JSX.Element {
  return (
    <aside className={`as-panel as-panel-left cad-panel cad-tools ${className}`.trim()}>
      {title ? <div className="as-panel-title">{title}</div> : null}
      {children}
    </aside>
  );
}

export function RightInspectorPanel({ children, className = "", title }: PanelProps): JSX.Element {
  return (
    <aside className={`as-panel as-panel-right cad-panel cad-inspector ${className}`.trim()}>
      {title ? <div className="as-panel-title">{title}</div> : null}
      {children}
    </aside>
  );
}

export function WorkspaceMain({ children }: PanelProps): JSX.Element {
  return <main className="as-workspace cad-workspace">{children}</main>;
}

export function DesignStatusBar({ children }: PanelProps): JSX.Element {
  return <div className="as-statusbar cad-statusbar">{children}</div>;
}
