import type { ReviewBundle, ReviewStage } from "../review/types";

interface ValidationPanelProps {
  stage: ReviewStage;
  bundle?: ReviewBundle;
}

export function ValidationPanel({ stage, bundle }: ValidationPanelProps): JSX.Element {
  const summary = bundle?.validationSummary;
  const findings = [...(stage.validationFindings ?? []), ...stage.warnings];
  return (
    <section className="validation-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Validation</span>
          <h2>Review Status</h2>
        </div>
        <strong className={`validation-label ${stage.validationStatus}`}>
          {stage.validationStatus === "pass" ? "Computed · no findings" : stage.validationStatus}
        </strong>
      </div>
      <div className="validation-metrics">
        <div>
          <strong>{stage.collisionCount}</strong>
          <span>Collisions</span>
        </div>
        <div>
          <strong>{stage.proximityCount}</strong>
          <span>Proximity</span>
        </div>
        <div>
          <strong>{stage.contactCount}</strong>
          <span>Contacts</span>
        </div>
      </div>
      {findings.length > 0 ? (
        <div className="validation-warning">{findings[0]}</div>
      ) : (
        <div className="validation-clear">Geometric checks ran; no findings were returned for this stage.</div>
      )}
      {summary && (
        <div className="validation-check-list">
          {(
            [
              ["geometry", "Geometry"],
              ["contacts", "Contacts"],
              ["proximity", "Proximity"],
              ["collisions", "Collisions"],
              ["movementConstraints", "Movement Constraints"],
              ["stageConsistency", "Stage Consistency"],
              ["dataCompleteness", "Data Completeness"],
              ["doctorReview", "Review Status"],
            ] as const
          ).map(([key, label]) => (
            <div className="validation-check-row" key={key}>
              <span>{label}</span>
              <strong>{summary[key].replaceAll("_", " ")}</strong>
            </div>
          ))}
        </div>
      )}
      <p className="muted-copy">
        Geometric findings only. No clinical constraints or treatment approval are represented.
      </p>
    </section>
  );
}
