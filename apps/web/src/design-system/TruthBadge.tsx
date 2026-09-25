import type { ProductTruthPresentation, ProductTruthState } from "./truthState";
import { PRODUCT_TRUTH_LABELS } from "./truthState";

interface TruthBadgeProps {
  state: ProductTruthState;
  reason?: string;
  className?: string;
}

/** Dense clinical-CAD status chip for Verified / Computed / Requires Review / Not Available. */
export function TruthBadge({ state, reason, className = "" }: TruthBadgeProps): JSX.Element {
  return (
    <span className={`as-truth-badge as-truth-${state} ${className}`.trim()} role="status" title={reason}>
      {PRODUCT_TRUTH_LABELS[state]}
      {reason ? <small className="as-truth-reason">{reason}</small> : null}
    </span>
  );
}

interface TruthPresentationBadgeProps {
  presentation: ProductTruthPresentation;
  className?: string;
}

export function TruthPresentationBadge({
  presentation,
  className = "",
}: TruthPresentationBadgeProps): JSX.Element {
  return (
    <TruthBadge state={presentation.state} reason={presentation.reason} className={className} />
  );
}
