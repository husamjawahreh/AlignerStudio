import type { DataProvenance } from "@alignerstudio/contracts";
import { TruthPresentationBadge } from "../design-system";
import { truthFromProvenance } from "../design-system/truthState";

interface FixtureBadgeProps {
  fixture: boolean;
  provenance: DataProvenance;
  notes?: string;
  sourceKind?: string;
}

const PROVENANCE_LABEL: Record<DataProvenance, string> = {
  real: "Real",
  generated: "Generated",
  experimental: "Experimental",
  fixture: "Fixture",
  clinically_reviewed: "Clinically Reviewed",
};

/** Doctor-facing truth badge. Engineering provenance labels stay test-only. */
export function FixtureBadge({ fixture, provenance, notes, sourceKind }: FixtureBadgeProps): JSX.Element {
  const presentation = truthFromProvenance({
    fixture,
    provenance,
  });
  return (
    <div className={`provenance-badge ${fixture ? "is-fixture" : ""}`} role="status">
      <TruthPresentationBadge presentation={presentation} />
      {sourceKind && <small className="technical-detail">Technical details available</small>}
      {import.meta.env.MODE === "test" && (
        <span className="production-test-metadata">
          {fixture ? "⚠ FIXTURE · not clinically valid" : PROVENANCE_LABEL[provenance]}
        </span>
      )}
      {notes && <small>{notes}</small>}
    </div>
  );
}
