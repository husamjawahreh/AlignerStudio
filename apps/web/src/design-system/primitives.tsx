import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  type = "button",
  ...rest
}: ButtonProps): JSX.Element {
  return (
    <button
      type={type}
      className={`as-btn as-btn-${variant} as-btn-${size} ${className}`.trim()}
      {...rest}
    />
  );
}

interface SegmentedControlOption<T extends string> {
  value: T;
  label: string;
  disabled?: boolean;
}

interface SegmentedControlProps<T extends string> {
  value: T;
  options: readonly SegmentedControlOption<T>[];
  onChange: (value: T) => void;
  ariaLabel: string;
}

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
}: SegmentedControlProps<T>): JSX.Element {
  return (
    <div className="as-segmented" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`as-segmented-item ${option.value === value ? "is-active" : ""}`}
          aria-pressed={option.value === value}
          disabled={option.disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

interface StatusBadgeProps {
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
  children: ReactNode;
}

export function StatusBadge({ tone = "neutral", children }: StatusBadgeProps): JSX.Element {
  return <span className={`as-status-badge as-status-${tone}`}>{children}</span>;
}

interface PropertyRowProps {
  label: string;
  children: ReactNode;
  hint?: string;
}

export function PropertyRow({ label, children, hint }: PropertyRowProps): JSX.Element {
  return (
    <div className="as-property-row">
      <div className="as-property-label">
        <span>{label}</span>
        {hint ? <small>{hint}</small> : null}
      </div>
      <div className="as-property-value">{children}</div>
    </div>
  );
}

interface NumericInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  unit?: string;
}

export function NumericInput({ unit, className = "", ...rest }: NumericInputProps): JSX.Element {
  return (
    <label className={`as-numeric-input ${className}`.trim()}>
      <input type="number" {...rest} />
      {unit ? <small>{unit}</small> : null}
    </label>
  );
}

interface SliderProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
}

export function Slider({ label, className = "", ...rest }: SliderProps): JSX.Element {
  return (
    <label className={`as-slider ${className}`.trim()}>
      <span>{label}</span>
      <input type="range" {...rest} />
    </label>
  );
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
}

export function Select({ label, className = "", children, ...rest }: SelectProps): JSX.Element {
  const control = (
    <select className={`as-select ${className}`.trim()} {...rest}>
      {children}
    </select>
  );
  if (!label) return control;
  return (
    <label className="as-field">
      <span>{label}</span>
      {control}
    </label>
  );
}

interface TabsProps {
  tabs: readonly { id: string; label: string; disabled?: boolean }[];
  activeId: string;
  onChange: (id: string) => void;
}

export function Tabs({ tabs, activeId, onChange }: TabsProps): JSX.Element {
  return (
    <div className="as-tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === activeId}
          className={`as-tab ${tab.id === activeId ? "is-active" : ""}`}
          disabled={tab.disabled}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  message: string;
  action?: ReactNode;
}

export function EmptyState({ title, message, action }: EmptyStateProps): JSX.Element {
  return (
    <div className="as-empty-state" role="status">
      <strong>{title}</strong>
      <p>{message}</p>
      {action}
    </div>
  );
}

interface UnavailableStateProps {
  title: string;
  message: string;
}

export function DesignUnavailableState({ title, message }: UnavailableStateProps): JSX.Element {
  return (
    <div className="as-unavailable-state" role="status">
      <span className="as-unavailable-mark" aria-hidden>
        !
      </span>
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}

interface LoadingStateProps {
  title: string;
  detail?: string;
}

export function LoadingState({ title, detail }: LoadingStateProps): JSX.Element {
  return (
    <div className="as-loading-state" role="status" aria-live="polite">
      <span className="as-loading-pulse" aria-hidden />
      <div>
        <strong>{title}</strong>
        {detail ? <p>{detail}</p> : null}
      </div>
    </div>
  );
}

interface ErrorStateProps {
  title: string;
  message: string;
  action?: ReactNode;
}

export function ErrorState({ title, message, action }: ErrorStateProps): JSX.Element {
  return (
    <div className="as-error-state" role="alert">
      <strong>{title}</strong>
      <p>{message}</p>
      {action}
    </div>
  );
}

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Accessible confirmation dialog foundation (no third-party modal dependency). */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
}: ConfirmDialogProps): JSX.Element | null {
  if (!open) return null;
  return (
    <div className="as-dialog-backdrop" role="presentation">
      <div className="as-dialog" role="dialog" aria-modal="true" aria-labelledby="as-dialog-title">
        <h2 id="as-dialog-title">{title}</h2>
        <p>{message}</p>
        <div className="as-dialog-actions">
          <Button variant="ghost" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant="primary" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

interface TooltipProps {
  text: string;
  children: ReactNode;
}

export function Tooltip({ text, children }: TooltipProps): JSX.Element {
  return (
    <span className="as-tooltip-wrap" title={text} data-tooltip={text}>
      {children}
    </span>
  );
}

interface ToolGroupProps {
  label: string;
  children: ReactNode;
}

export function ToolGroup({ label, children }: ToolGroupProps): JSX.Element {
  return (
    <section className="as-tool-group" aria-label={label}>
      <span className="as-tool-group-label">{label}</span>
      <div className="as-tool-group-body">{children}</div>
    </section>
  );
}

interface AdvancedDetailsProps {
  summary?: string;
  children: ReactNode;
  defaultOpen?: boolean;
}

/** Progressive disclosure for Level 3–4 technical / provenance content. */
export function AdvancedDetails({
  summary = "Advanced details",
  children,
  defaultOpen = false,
}: AdvancedDetailsProps): JSX.Element {
  return (
    <details className="as-advanced-details" open={defaultOpen} data-testid="advanced-details">
      <summary>{summary}</summary>
      <div className="as-advanced-details-body">{children}</div>
    </details>
  );
}

interface CurrentTargetPairProps {
  currentLabel?: string;
  targetLabel?: string;
  currentValue: ReactNode;
  targetValue: ReactNode;
  targetAvailable?: boolean;
}

/** Clear CURRENT vs TARGET presentation without fabricating target values. */
export function CurrentTargetPair({
  currentLabel = "Current",
  targetLabel = "Target",
  currentValue,
  targetValue,
  targetAvailable = true,
}: CurrentTargetPairProps): JSX.Element {
  return (
    <div className="as-current-target" data-testid="current-target-pair">
      <div className="as-current-target-col is-current">
        <span className="eyebrow">{currentLabel}</span>
        <strong>{currentValue}</strong>
      </div>
      <div className={`as-current-target-col is-target ${targetAvailable ? "" : "is-unavailable"}`}>
        <span className="eyebrow">{targetLabel}</span>
        <strong>{targetAvailable ? targetValue : "Not Available"}</strong>
      </div>
    </div>
  );
}

