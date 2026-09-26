import type { ReactNode } from "react";
import type {
  ReviewBundle,
  TreatmentSetupComparison,
  TreatmentSetupVersionMeta,
} from "../review/types";
import {
  buildSetupComparison,
  buildTreatmentSetupSummary,
} from "../treatmentWorkflowPresentation";

interface TreatmentSetupPanelProps {
  bundle: ReviewBundle;
  bothArchesValid: boolean;
  backendTreatment: boolean;
  showOriginal: boolean;
  showTargetGhost: boolean;
  originalOpacity: number;
  treatmentAvailable: boolean;
  versionCompare?: TreatmentSetupComparison | null;
  onGeneratePlan: () => void;
  /** Primary only when this is the canonical next action. */
  emphasizeCreate?: boolean;
  onToggleInitialPosition: (visible: boolean) => void;
  onToggleTargetPosition: (visible: boolean) => void;
  onOriginalOpacityChange: (value: number) => void;
  onSelectAlternative?: (alternativeId: string) => void;
  onSaveVersion?: (description: string) => void;
  onRestoreVersion?: (versionId: string) => void;
  onCompareVersions?: (leftVersionId: string, rightVersionId: string) => void;
}

/** Treatment Setup 2.0 — CURRENT / TARGET / VERSION over WP-03 workspace data. */
export function TreatmentSetupPanel({
  bundle,
  bothArchesValid,
  backendTreatment,
  showOriginal,
  showTargetGhost,
  originalOpacity,
  treatmentAvailable,
  versionCompare = null,
  onGeneratePlan,
  emphasizeCreate = false,
  onToggleInitialPosition,
  onToggleTargetPosition,
  onOriginalOpacityChange,
  onSelectAlternative,
  onSaveVersion,
  onRestoreVersion,
  onCompareVersions,
}: TreatmentSetupPanelProps): JSX.Element {
  const summary = buildTreatmentSetupSummary(bundle);
  const comparison = buildSetupComparison(bundle.stages[0], bundle.stages.at(-1));
  const setup = bundle.treatmentSetup;
  const versions = setup?.versions ?? [];
  const readiness = setup?.readiness;
  const currentVsTarget = setup?.current_vs_target;

  return (
    <div className="treatment-setup-panel case-form" data-testid="treatment-setup-panel">
      <section className="analysis-section" aria-labelledby="treatment-setup-heading">
        <h3 id="treatment-setup-heading" className="eyebrow">
          Treatment Setup 2.0
        </h3>
        {treatmentAvailable ? (
          <p className="cad-review-note" data-testid="treatment-plan-stored">
            A treatment plan is stored. Opening this step does not rebuild staging or validation.
          </p>
        ) : (
          <>
            <p className="cad-review-note" data-testid="treatment-target-empty">
              No treatment target yet. Opening this step does not create a plan.
            </p>
            <button
              aria-label="Generate Treatment Setup"
              className={emphasizeCreate ? "primary-button" : "secondary-button"}
              onClick={onGeneratePlan}
              disabled={!bothArchesValid || backendTreatment}
            >
              Create Treatment Plan
            </button>
          </>
        )}
        <div className="cad-stat-row">
          <span>Target setup</span>
          <strong>{summary.available ? "Available" : "Unavailable"}</strong>
        </div>
        <div className="cad-stat-row" data-testid="setup-layer-source">
          <span>SOURCE</span>
          <strong>Immutable</strong>
        </div>
        <div className="cad-stat-row" data-testid="setup-layer-current">
          <span>CURRENT</span>
          <strong>{setup?.layers.current ? "Equals source (FV)" : "Unavailable"}</strong>
        </div>
        <div className="cad-stat-row" data-testid="setup-layer-target">
          <span>TARGET</span>
          <strong>
            {setup
              ? `${setup.moved_tooth_count} changed · ${setup.proposal_kind.replaceAll("_", " ")}`
              : "Unavailable"}
          </strong>
        </div>
        <small className="cad-review-note">
          Target transforms are not clinical approval. No clinically approved state is exposed.
        </small>
      </section>

      <section className="analysis-section" aria-labelledby="initial-position">
        <h3 id="initial-position" className="eyebrow">
          Initial / Current Position
        </h3>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showOriginal}
            onChange={(event) => onToggleInitialPosition(event.target.checked)}
          />
          <span>Show Initial Position</span>
        </label>
        {showOriginal && (
          <label className="range-row">
            <span>Opacity</span>
            <input
              type="range"
              min="0.08"
              max="0.75"
              step="0.01"
              value={originalOpacity}
              onChange={(event) => onOriginalOpacityChange(Number(event.target.value))}
            />
          </label>
        )}
        <div className="cad-stat-row">
          <span>Stage</span>
          <strong>{summary.initialStageLabel}</strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="target-position">
        <h3 id="target-position" className="eyebrow">
          Target Position
        </h3>
        <label className="toggle-row">
          <input
            type="checkbox"
            checked={showTargetGhost}
            disabled={!treatmentAvailable}
            onChange={(event) => onToggleTargetPosition(event.target.checked)}
          />
          <span>Show Target Position</span>
        </label>
        <div className="cad-stat-row">
          <span>Stage</span>
          <strong>{summary.targetStageLabel}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Working version</span>
          <strong data-testid="setup-working-version">
            {bundle.versionId ? bundle.versionId.slice(0, 12) : "Unavailable"}
          </strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="tooth-movement">
        <h3 id="tooth-movement" className="eyebrow">
          Tooth Movement
        </h3>
        <div className="cad-stat-row">
          <span>Moved teeth</span>
          <strong>
            {summary.movedToothCount === null ? "Unavailable" : summary.movedToothCount}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Total movement</span>
          <strong>
            {summary.totalMovement === null ? "Unavailable" : summary.totalMovement.toFixed(3)}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Constraints</span>
          <strong>
            {(setup?.constraint_availability ?? "unavailable").replaceAll("_", " ")}
          </strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="setup-comparison">
        <h3 id="setup-comparison" className="eyebrow">
          Current vs Target
        </h3>
        <small className="cad-review-note">
          Geometric deltas only — not clinical intrusion/tip/torque claims.
        </small>
        {(currentVsTarget?.changed_teeth.length ?? 0) === 0 && comparison.length === 0 ? (
          <small className="cad-review-note">No comparable movement rows yet.</small>
        ) : (
          (currentVsTarget?.changed_teeth ?? [])
            .slice(0, 12)
            .map((row) => (
              <div className="cad-stat-row" key={row.tooth_key}>
                <span>
                  {row.tooth_ref ?? row.tooth_key}
                  {row.arch ? ` · ${row.arch}` : ""}
                </span>
                <strong>
                  Δxyz{" "}
                  {row.translation_delta.map((value) => value.toFixed(2)).join(", ")}
                </strong>
              </div>
            ))
        )}
        {!currentVsTarget &&
          comparison.map((row) => (
            <div className="cad-stat-row" key={row.toothKey}>
              <span>
                {row.label} · {row.arch}
              </span>
              <strong>{row.targetMovement.toFixed(3)}</strong>
            </div>
          ))}
      </section>

      {readiness && (
        <section className="analysis-section" aria-labelledby="setup-readiness" data-testid="setup-readiness">
          <h3 id="setup-readiness" className="eyebrow">
            Readiness
          </h3>
          <small className="cad-review-note">Capability gates — not an AI score.</small>
          {(
            [
              ["Geometry", readiness.real_geometry],
              ["Identity", readiness.identity],
              ["Arch", readiness.arch],
              ["Transform", readiness.transform],
              ["Constraints", readiness.constraint],
              ["Validation", readiness.validation],
              ["Occlusion", readiness.occlusion],
              ["Clinical axes", readiness.clinical_axes],
            ] as const
          ).map(([label, state]) => (
            <div className="cad-stat-row" key={label}>
              <span>{label}</span>
              <strong>{state.replaceAll("_", " ")}</strong>
            </div>
          ))}
        </section>
      )}

      <section className="analysis-section" aria-labelledby="plan-versions" data-testid="setup-versions">
        <h3 id="plan-versions" className="eyebrow">
          VERSION
        </h3>
        <div className="cad-stat-row">
          <span>Setup plan</span>
          <strong>{bundle.setupPlanId ?? "Unavailable"}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Parent</span>
          <strong>
            {bundle.parentVersionId ? bundle.parentVersionId.slice(0, 12) : "None"}
          </strong>
        </div>
        {onSaveVersion && (
          <button
            className="secondary-button"
            type="button"
            disabled={!treatmentAvailable}
            onClick={() => onSaveVersion("Doctor-saved treatment setup version")}
            data-testid="setup-save-version"
          >
            Save version
          </button>
        )}
        {versions.length === 0 ? (
          <small className="cad-review-note">No saved versions yet.</small>
        ) : (
          versions.map((version: TreatmentSetupVersionMeta, index) => (
            <div className="proposal-row" key={version.version_id}>
              <div className="proposal-row-header">
                <strong title={version.version_id}>
                  {version.version_id.slice(0, 10)}…
                </strong>
                <span className="proposal-status">
                  {version.proposal_kind.replaceAll("_", " ")}
                </span>
              </div>
              <div className="proposal-values">
                <span>{version.change_summary}</span>
                <span>Moved {version.moved_tooth_count}</span>
                <span>Validation {version.validation_status ?? "unavailable"}</span>
                <span>{version.author_source}</span>
              </div>
              <div className="proposal-actions">
                {onRestoreVersion && (
                  <button
                    className="text-button"
                    type="button"
                    onClick={() => onRestoreVersion(version.version_id)}
                  >
                    Restore
                  </button>
                )}
                {onCompareVersions && index > 0 && (
                  <button
                    className="text-button"
                    type="button"
                    onClick={() =>
                      onCompareVersions(versions[index - 1].version_id, version.version_id)
                    }
                  >
                    Compare prior
                  </button>
                )}
              </div>
            </div>
          ))
        )}
        {versionCompare && (
          <div data-testid="setup-version-compare">
            <small className="cad-review-note">
              Compare {versionCompare.left_version_id.slice(0, 8)}… vs{" "}
              {versionCompare.right_version_id.slice(0, 8)}… · changed{" "}
              {versionCompare.changed_count} · unchanged {versionCompare.unchanged_count}
            </small>
            {versionCompare.changed_teeth.slice(0, 8).map((row) => (
              <div className="cad-stat-row" key={row.tooth_key}>
                <span>{row.tooth_ref ?? row.tooth_key}</span>
                <strong>
                  Δ {row.translation_delta.map((value) => value.toFixed(2)).join(", ")}
                </strong>
              </div>
            ))}
          </div>
        )}
        <div className="cad-stat-row">
          <span>Setup alternatives</span>
          <strong>{summary.setupAlternativesLabel}</strong>
        </div>
      </section>

      {bundle.planningIntelligence && (
        <section className="analysis-section" aria-labelledby="planning-intelligence">
          <h3 id="planning-intelligence" className="eyebrow">
            Planning Intelligence
          </h3>
          <small className="cad-review-note">{bundle.planningIntelligence.rule}</small>
          <div className="cad-stat-row">
            <span>Landmark-assisted</span>
            <strong>
              {bundle.planningIntelligence.landmarkAssistedTargetSetup.replaceAll("_", " ")}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Arch-form-aware</span>
            <strong>
              {bundle.planningIntelligence.archFormAwarePlanning.replaceAll("_", " ")}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Occlusion-aware</span>
            <strong>
              {bundle.planningIntelligence.occlusionAwarePlanning.replaceAll("_", " ")}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Collision-aware</span>
            <strong>
              {bundle.planningIntelligence.collisionAwareCandidateGeneration.replaceAll(
                "_",
                " ",
              )}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Constrained 6-DOF</span>
            <strong>
              {bundle.planningIntelligence.constrainedSixDofTrajectories.replaceAll("_", " ")}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Staging proposals</span>
            <strong>
              {bundle.planningIntelligence.stagingProposals.replaceAll("_", " ")}
            </strong>
          </div>
          {bundle.planningIntelligence.alternatives.map((alternative) => (
            <div className="proposal-row" key={alternative.alternativeId}>
              <div className="proposal-row-header">
                <strong>{alternative.label}</strong>
                <span className={`proposal-status ${alternative.isActive ? "accepted" : ""}`}>
                  {alternative.isActive ? "active" : alternative.contract.decisionState.replaceAll("_", " ")}
                </span>
              </div>
              <div className="proposal-values">
                <span>Model {alternative.contract.modelName}</span>
                <span>v{alternative.contract.modelVersion}</span>
                <span>
                  Confidence{" "}
                  {alternative.contract.confidence === null
                    ? "not provided"
                    : alternative.contract.confidence}
                </span>
                <span>Validation {alternative.contract.deterministicValidationStatus}</span>
                <span>
                  Collisions {alternative.collisionCount} · Stages {alternative.stageCount}
                </span>
              </div>
              {onSelectAlternative &&
                !alternative.isActive &&
                alternative.contract.decisionState !== "rejected_by_validation" && (
                  <div className="proposal-actions">
                    <button
                      className="text-button"
                      onClick={() => onSelectAlternative(alternative.alternativeId)}
                    >
                      Accept setup
                    </button>
                  </div>
                )}
            </div>
          ))}
          {bundle.planningIntelligence.researchAdapters.map((adapter) => (
            <div className="cad-stat-row" key={adapter.adapterId}>
              <span>{adapter.modelName}</span>
              <strong>{adapter.status.replaceAll("_", " ")}</strong>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

interface TreatmentSetupInspectorProps {
  bundle: ReviewBundle;
  treatmentAvailable: boolean;
  children?: ReactNode;
}

export function TreatmentSetupInspector({
  bundle,
  treatmentAvailable,
  children,
}: TreatmentSetupInspectorProps): JSX.Element {
  const summary = buildTreatmentSetupSummary(bundle);
  const setup = bundle.treatmentSetup;
  return (
    <>
      <div className="cad-inspector-section" data-testid="treatment-setup-inspector">
        <span className="eyebrow">Treatment Setup 2.0</span>
        <h2>{treatmentAvailable ? "Target Position ready" : "Setup unavailable"}</h2>
        <p>
          {treatmentAvailable
            ? "SOURCE · CURRENT · TARGET separated. Edits are reversible and versioned."
            : "Run analysis and generate a Treatment Setup."}
        </p>
        <div className="cad-stat-row">
          <span>Tooth Movement</span>
          <strong>
            {summary.movedToothCount === null ? "Unavailable" : summary.movedToothCount}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>VERSION</span>
          <strong>
            {bundle.versionId ? bundle.versionId.slice(0, 12) : summary.planVersionLabel}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Saved versions</span>
          <strong>{setup?.versions.length ?? 0}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Proposal</span>
          <strong>{summary.proposalKind}</strong>
        </div>
        <small className="cad-review-note">
          Doctor edits are not clinical approval. Staging / IPR / attachments remain out of scope.
        </small>
      </div>
      {children}
    </>
  );
}
