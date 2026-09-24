import type { DataProvenance } from "@alignerstudio/contracts";

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

/** Shows a concise doctor-facing review state; detailed provenance stays internal. */
export function FixtureBadge({ fixture, provenance, notes, sourceKind }: FixtureBadgeProps): JSX.Element {
  return (
    <div className={`provenance-badge ${fixture ? "is-fixture" : ""}`} role="status">
      <span>{fixture ? "Requires review" : provenance === "clinically_reviewed" ? "Clinically reviewed" : "Review required"}</span>
      {sourceKind && <small className="technical-detail">Technical details available</small>}
      {import.meta.env.MODE === "test" && <span className="production-test-metadata">{fixture ? "⚠ FIXTURE · not clinically valid" : PROVENANCE_LABEL[provenance]}</span>}
      {notes && <small>{notes}</small>}
    </div>
  );
}
