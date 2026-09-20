import type { ReviewStage } from "../review/types";

interface ValidationPanelProps {
  stage: ReviewStage;
}

export function ValidationPanel({ stage }: ValidationPanelProps): JSX.Element {
  return (
    <section className="validation-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Geometry review</span>
          <h2>Stage validation</h2>
        </div>
        <strong className={`validation-label ${stage.validationStatus}`}>
          {stage.validationStatus}
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
      {stage.warnings.length > 0 ? (
        <div className="validation-warning">{stage.warnings[0]}</div>
      ) : (
        <div className="validation-clear">No geometric findings in this stage.</div>
      )}
      <p className="muted-copy">
        Geometric findings only. No clinical constraints or treatment approval are represented.
      </p>
    </section>
  );
}
