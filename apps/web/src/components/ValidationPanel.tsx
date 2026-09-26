import type { ReviewBundle, ReviewStage } from "../review/types";

interface ValidationPanelProps {
  stage: ReviewStage;
  bundle?: ReviewBundle;
}

function formatState(value: string | null | undefined): string {
  if (!value) return "Not Available";
  return value.replaceAll("_", " ");
}

export function ValidationPanel({ stage, bundle }: ValidationPanelProps): JSX.Element {
  const summary = bundle?.validationSummary;
  const capability = bundle?.validationCapability;
  const findings = [...(stage.validationFindings ?? []), ...stage.warnings];
  const checks = capability?.checks ?? [];
  const runFindings = capability?.findings ?? [];
  const unavailableChecks = checks.filter((item) => item.check_state === "not_available");
  const reviewChecks = checks.filter((item) => item.check_state === "requires_review");
  const stageFindings = runFindings.filter(
    (item) => item.stage_index === stage.index || item.stage_index == null,
  );

  return (
    <section className="validation-panel" data-testid="validation-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Validation 2.0</span>
          <h2>Review Status</h2>
        </div>
        <strong
          className={`validation-label ${stage.validationStatus}`}
          data-testid="validation-stage-status"
        >
          {stage.validationStatus === "pass"
            ? "Computed · no findings"
            : stage.validationStatus}
        </strong>
      </div>

      {capability && (
        <div className="validation-metrics" data-testid="validation-capability-summary">
          <div>
            <strong>{capability.summary.checks_passed}</strong>
            <span>Passed</span>
          </div>
          <div>
            <strong>{capability.summary.warnings}</strong>
            <span>Warnings</span>
          </div>
          <div>
            <strong>{capability.summary.errors}</strong>
            <span>Errors</span>
          </div>
          <div>
            <strong>{capability.summary.unavailable_checks}</strong>
            <span>Unavailable</span>
          </div>
          <div>
            <strong>{capability.summary.review_required_checks}</strong>
            <span>Review</span>
          </div>
        </div>
      )}

      <p className="cad-review-note">
        {capability
          ? "A validation run is stored. Unavailable checks are not a pass, and this is not a clinical approval."
          : "No validation run for this treatment version. A missing check is not a pass."}
      </p>

      {!capability && (
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
      )}

      {capability && (
        <div className="cad-stat-row">
          <span>Freshness</span>
          <strong data-testid="validation-freshness">
            {formatState(capability.freshness)}
          </strong>
        </div>
      )}
      {capability && (
        <div className="cad-stat-row">
          <span>Overall</span>
          <strong data-testid="validation-overall-state">
            {formatState(capability.overall_check_state)} ·{" "}
            {formatState(capability.overall_truth_state)}
          </strong>
        </div>
      )}
      {capability && (
        <div className="cad-stat-row">
          <span>Run</span>
          <strong data-testid="validation-run-id">{capability.validation_run_id}</strong>
        </div>
      )}

      {findings.length > 0 ? (
        <div className="validation-warning">{findings[0]}</div>
      ) : (
        <div className="validation-clear">
          Geometric checks ran for this stage; no stage findings were returned. This is not
          clinical approval.
        </div>
      )}

      {checks.length > 0 && (
        <details className="validation-check-catalog-fold" data-testid="validation-check-catalog">
          <summary>All checks ({checks.length})</summary>
          <div className="validation-check-list">
            {checks.map((check) => (
              <div className="validation-check-row" key={check.check_id}>
                <span>{check.label}</span>
                <strong>{formatState(check.check_state)}</strong>
              </div>
            ))}
          </div>
        </details>
      )}

      {unavailableChecks.length > 0 && (
        <div className="validation-check-list" data-testid="validation-unavailable-checks">
          <strong className="eyebrow">Unavailable</strong>
          {unavailableChecks.map((check) => (
            <div className="validation-check-row" key={`na-${check.check_id}`}>
              <span>{check.label}</span>
              <strong>not available</strong>
            </div>
          ))}
        </div>
      )}

      {reviewChecks.length > 0 && (
        <div className="validation-check-list" data-testid="validation-review-checks">
          <strong className="eyebrow">Requires review</strong>
          {reviewChecks.map((check) => (
            <div className="validation-check-row" key={`rr-${check.check_id}`}>
              <span>{check.label}</span>
              <strong>requires review</strong>
            </div>
          ))}
        </div>
      )}

      {stageFindings.length > 0 && (
        <div className="validation-check-list" data-testid="validation-findings-list">
          <strong className="eyebrow">Findings</strong>
          {stageFindings.slice(0, 8).map((finding) => (
            <div className="validation-check-row" key={finding.finding_id}>
              <span>
                {finding.category}
                {finding.affected_tooth_refs?.length
                  ? ` · ${finding.affected_tooth_refs.join("/")}`
                  : ""}
                {finding.stage_index != null ? ` · stage ${finding.stage_index}` : ""}
              </span>
              <strong>{formatState(finding.check_state)}</strong>
            </div>
          ))}
        </div>
      )}

      {summary && !capability && (
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
              ["provenance", "Provenance"],
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

      {capability && (
        <div className="cad-stat-row">
          <span>Provenance</span>
          <strong>
            {capability.provenance} · {capability.geometric_engine_version ?? "n/a"}
          </strong>
        </div>
      )}

      <p className="muted-copy">
        Technical validation only. PASS is not clinical approval or clinical safety. Unavailable
        checks stay unavailable and are never treated as pass.
      </p>
    </section>
  );
}
