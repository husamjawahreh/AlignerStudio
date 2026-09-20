import type { DataProvenance } from "@alignerstudio/contracts";

interface FixtureBadgeProps {
  fixture: boolean;
  provenance: DataProvenance;
  notes?: string;
}

const PROVENANCE_LABEL: Record<DataProvenance, string> = {
  real: "Real",
  generated: "Generated",
  experimental: "Experimental",
  fixture: "Fixture",
  clinically_reviewed: "Clinically Reviewed",
};

/** Visibly flags fixture/non-clinical data so it can never be mistaken for real output. */
export function FixtureBadge({ fixture, provenance, notes }: FixtureBadgeProps): JSX.Element {
  return (
    <div className={`provenance-badge ${fixture ? "is-fixture" : ""}`} role="status">
      <span>{fixture ? "⚠ FIXTURE · not clinically valid" : PROVENANCE_LABEL[provenance]}</span>
      {!fixture && <span className="provenance-value">{PROVENANCE_LABEL[provenance]}</span>}
      {notes && <small>{notes}</small>}
    </div>
  );
}
