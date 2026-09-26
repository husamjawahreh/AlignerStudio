import type { CaseDentalIntelligencePayload, MeshValidationResult } from "@alignerstudio/contracts";
import type { PipelineDiagnostic } from "../api/client";
import type { ReviewToothMesh } from "../review/types";
import {
  buildAnalysisFindings,
  buildAnalysisOverview,
  formatAvailability,
  formatMeshMeasurement,
  formatOcclusionAvailability,
  formatTruthState,
} from "../analysisPresentation";
import { AdvancedDetails } from "../design-system";
import { toothReviewLabel } from "../interaction/model";

interface AnalysisPanelProps {
  bothArchesValid: boolean;
  diagnostic: PipelineDiagnostic | null;
  dentalIntelligence?: CaseDentalIntelligencePayload | null;
  teeth: readonly ReviewToothMesh[];
  validation: MeshValidationResult | null;
  hiddenToothIds: ReadonlySet<number>;
  onAnalyzeCase: () => void;
  onToggleToothVisibility: (instanceId: number) => void;
  emphasizeRun?: boolean;
  /** Environment blocker. The review button must not look like a retry. */
  runBlocked?: boolean;
  fixtureOnly?: boolean;
}

/** Analysis left tools — Master Plan labels; only existing diagnostic data. */
export function AnalysisPanel({
  bothArchesValid,
  diagnostic,
  dentalIntelligence = null,
  teeth,
  validation,
  hiddenToothIds,
  onAnalyzeCase,
  onToggleToothVisibility,
  emphasizeRun = true,
  runBlocked = false,
  fixtureOnly = false,
}: AnalysisPanelProps): JSX.Element {
  const overview = buildAnalysisOverview({ diagnostic, teeth, dentalIntelligence });
  const findings = buildAnalysisFindings({ diagnostic, validation, dentalIntelligence });

  return (
    <div className="analysis-panel case-form" data-testid="analysis-panel">
      <section className="analysis-section" aria-labelledby="analysis-run">
        <h3 id="analysis-run" className="eyebrow">
          Tooth Segmentation
        </h3>
        {fixtureOnly ? (
          <p className="cad-review-note" data-testid="analysis-fixture-note">
            Test-only segmentation. This is not a patient result.
          </p>
        ) : null}
        {runBlocked ? (
          <p className="cad-review-note" data-testid="analysis-environment-block">
            Segmentation cannot be completed on this computer. This is not a failed scan and not zero teeth.
          </p>
        ) : null}
        <button
          aria-label="Review segmentation"
          className={emphasizeRun && !runBlocked ? "primary-button" : "secondary-button"}
          onClick={onAnalyzeCase}
          disabled={!bothArchesValid || runBlocked}
          data-testid={emphasizeRun && !runBlocked ? "primary-next-action" : undefined}
          title={
            runBlocked
              ? "Retry is unavailable until this computer can run segmentation."
              : "Runs segmentation review. Opening this step does not start it."
          }
        >
          Analyze case
        </button>
        <p className="cad-review-note">
          Segmentation status, counts, and provenance are on the review strip. Identity that is not established is not numbered.
        </p>
        {overview.overallTruthState && (
          <div className="cad-stat-row">
            <span>Review</span>
            <strong data-testid="intelligence-overall-truth">
              {formatTruthState(overview.overallTruthState)}
            </strong>
          </div>
        )}
        {overview.identityReadiness && (
          <div className="cad-stat-row">
            <span>Identity</span>
            <strong data-testid="identity-readiness">
              {formatTruthState(overview.identityReadiness)}
            </strong>
          </div>
        )}
      </section>

      <section className="analysis-section" aria-labelledby="analysis-tooth-id">
        <h3 id="analysis-tooth-id" className="eyebrow">
          Identification
        </h3>
        <div className="cad-stat-row">
          <span>Identified</span>
          <strong>
            {overview.countsAvailable && overview.identifiedTeeth !== null
              ? overview.identifiedTeeth
              : "Not available"}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Uncertain</span>
          <strong>
            {overview.countsAvailable && overview.uncertainTeeth !== null
              ? overview.uncertainTeeth
              : "Not available"}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Unresolved</span>
          <strong>
            {overview.countsAvailable && overview.unidentifiedTeeth !== null
              ? overview.unidentifiedTeeth
              : "Not available"}
          </strong>
        </div>
        {teeth.length > 0 ? (
          <AdvancedDetails summary="Tooth visibility">
            <div className="cad-tooth-map" data-testid="toothinstancenet-summary">
              <strong>{teeth.length} meshes</strong>
              <small>FDI only when persisted identity is authoritative. Otherwise tooth_ref.</small>
              {diagnostic?.fixture && import.meta.env.MODE === "test" && (
                <span className="production-test-metadata">
                  Validated real-case fixture FIXTURE · not clinically valid
                </span>
              )}
              {teeth.map((tooth) => {
                const toothIntel = dentalIntelligence?.teeth.find(
                  (item) => item.instance_id === tooth.instanceId && item.arch === tooth.arch,
                );
                const fdiState = toothIntel?.fdi_number.state;
                return (
                  <label className="toggle-row" key={`${tooth.arch}-${tooth.instanceId}`}>
                    <input
                      type="checkbox"
                      checked={!hiddenToothIds.has(tooth.instanceId)}
                      onChange={() => onToggleToothVisibility(tooth.instanceId)}
                    />
                    <span>
                      {toothReviewLabel(tooth).text}
                      {fdiState ? ` · ${formatTruthState(fdiState)}` : ""}
                      {toothReviewLabel(tooth).unresolved ? " · unresolved" : ""}
                    </span>
                  </label>
                );
              })}
            </div>
          </AdvancedDetails>
        ) : (
          <small className="cad-review-note">
            {runBlocked
              ? "Segmentation unavailable on this computer. This is not a list of missing teeth."
              : "No segmentation meshes are stored yet."}
          </small>
        )}
      </section>

      <AdvancedDetails summary="Advanced details">
      <section className="analysis-section" aria-labelledby="analysis-arch">
        <h3 id="analysis-arch" className="eyebrow">
          Arch Analysis
        </h3>
        <div className="cad-stat-row">
          <span>Arch analysis</span>
          <strong>{formatAvailability(overview.archAnalysisAvailable)}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Orientation</span>
          <strong>{formatAvailability(overview.archOrientationAvailable)}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Arch form</span>
          <strong>
            {overview.archTotalWidth === null
              ? formatAvailability(overview.archFormAvailable)
              : `width ${overview.archTotalWidth.toFixed(3)}`}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Midline</span>
          <strong>{formatAvailability(overview.midlineAvailable)}</strong>
        </div>
      </section>

      <section className="analysis-section" aria-labelledby="analysis-occlusion">
        <h3 id="analysis-occlusion" className="eyebrow">
          Occlusion
        </h3>
        <div className="cad-stat-row">
          <span>Occlusion</span>
          <strong data-testid="occlusion-truth">
            {overview.occlusionTruth
              ? formatTruthState(overview.occlusionTruth)
              : formatOcclusionAvailability(overview.occlusionAvailability)}
          </strong>
        </div>
        <p className="cad-review-note">Bite registration required for occlusion contacts.</p>
        <AdvancedDetails summary="Occlusion details">
          <div className="cad-stat-row">
            <span>Upper/lower registration</span>
            <strong>
              {formatOcclusionAvailability(
                diagnostic?.anatomical_intelligence?.occlusion.upper_lower_registration ?? null,
              )}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Bite record</span>
            <strong>
              {formatOcclusionAvailability(
                diagnostic?.anatomical_intelligence?.occlusion.bite_record ?? null,
              )}
            </strong>
          </div>
          <div className="cad-stat-row">
            <span>Occlusal contacts</span>
            <strong>
              {formatOcclusionAvailability(
                diagnostic?.anatomical_intelligence?.occlusion.occlusal_contacts ?? null,
              )}
            </strong>
          </div>
          {overview.occlusionCapabilityState && (
            <div className="cad-stat-row">
              <span>Capability</span>
              <strong data-testid="occlusion-capability-state">
                {overview.occlusionCapabilityState.replaceAll("_", " ")}
              </strong>
            </div>
          )}
          {overview.registrationState && (
            <div className="cad-stat-row">
              <span>Registration</span>
              <strong data-testid="registration-state">
                {overview.registrationState.replaceAll("_", " ")}
              </strong>
            </div>
          )}
        </AdvancedDetails>
      </section>

      <section className="analysis-section" aria-labelledby="analysis-advanced-anatomy">
        <h3 id="analysis-advanced-anatomy" className="eyebrow">
          Advanced Anatomy
        </h3>
        <div className="cad-stat-row">
          <span>Crown geometry</span>
          <strong data-testid="crown-anatomy-state">
            {formatTruthState(
              (overview.crownAnatomyState as "computed" | "not_available" | null) ?? null,
            )}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Root geometry</span>
          <strong data-testid="root-anatomy-state">
            {formatTruthState(
              (overview.rootAnatomyState as "not_available" | null) ?? overview.rootsTruth,
            )}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Landmark geometry</span>
          <strong data-testid="landmark-anatomy-state">
            {formatTruthState(
              (overview.landmarkAnatomyState as "not_available" | null) ?? overview.landmarksTruth,
            )}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Clinical dental axes</span>
          <strong data-testid="clinical-axes-anatomy-state">
            {formatTruthState(
              (overview.clinicalAxesAnatomyState as "not_available" | null) ??
                overview.clinicalAxesTruth,
            )}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Generic geometric directions</span>
          <strong data-testid="generic-axes-state">
            {formatTruthState(
              (overview.genericGeometricAxesState as "computed" | "not_available" | null) ?? null,
            )}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>CBCT / volumetric</span>
          <strong data-testid="cbct-anatomy-state">
            {formatTruthState(
              (overview.cbctAnatomyState as "not_available" | null) ?? null,
            )}
          </strong>
        </div>
        <small className="cad-review-note">
          Crown-only STL never fabricates roots, landmarks, clinical axes, or CBCT anatomy.
          Mesh PCA is geometric only.
        </small>
      </section>

      <section className="analysis-section" aria-labelledby="analysis-measurements">
        <h3 id="analysis-measurements" className="eyebrow">
          Measurements
        </h3>
        <div className="cad-stat-row">
          <span>Mesh triangles</span>
          <strong>{formatMeshMeasurement(validation)}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Landmarks</span>
          <strong data-testid="landmarks-truth">
            {overview.landmarksTruth
              ? formatTruthState(overview.landmarksTruth)
              : formatAvailability(overview.landmarksAvailable)}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Clinical dental axes</span>
          <strong data-testid="clinical-axes-truth">
            {formatTruthState(
              overview.clinicalAxesTruth ??
                (overview.clinicalAxesAnatomyState as "not_available" | null) ??
                null,
            )}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Root geometry</span>
          <strong data-testid="roots-truth">
            {overview.rootsTruth ? formatTruthState(overview.rootsTruth) : "Not Available"}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Movement reference frames</span>
          <strong>{formatAvailability(overview.movementFramesAvailable)}</strong>
        </div>
        <small className="cad-review-note">
          Mesh principal directions are geometric PCA and are not clinical dental axes.
        </small>
      </section>

      <section className="analysis-section" aria-labelledby="analysis-readiness">
        <h3 id="analysis-readiness" className="eyebrow">
          Capability readiness
        </h3>
        <div className="cad-stat-row">
          <span>Geometry</span>
          <strong>{formatTruthState(overview.geometryReadiness)}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Axes</span>
          <strong>{formatTruthState(overview.axisReadiness)}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Occlusion</span>
          <strong>{formatTruthState(overview.occlusionReadiness)}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Treatment setup</span>
          <strong data-testid="treatment-setup-readiness">
            {formatTruthState(overview.treatmentSetupReadiness)}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Validation</span>
          <strong>{formatTruthState(overview.validationReadiness)}</strong>
        </div>
        <small className="cad-review-note">
          Readiness signals are prerequisites, not clinical clearance or auto-unlock.
        </small>
      </section>

      <section className="analysis-section" aria-labelledby="analysis-data-quality">
        <h3 id="analysis-data-quality" className="eyebrow">
          Data Quality
        </h3>
        <div className="cad-stat-row">
          <span>Instances</span>
          <strong>{overview.instanceCount}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Identification confidence</span>
          <strong>
            {overview.identificationConfidence === null
              ? "Unavailable"
              : overview.identificationConfidence.toFixed(3)}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Scale validation</span>
          <strong>{overview.scaleValidation ?? "Unavailable"}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Units</span>
          <strong>{overview.units ?? "Unavailable"}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Mesh quality</span>
          <strong>
            {overview.meshQuality ??
              (validation ? (validation.is_watertight ? "watertight" : "non_watertight") : "Unavailable")}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Incomplete scans</span>
          <strong>
            {overview.incompleteScans === null
              ? "Unavailable"
              : overview.incompleteScans
                ? "Yes"
                : "No"}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Ambiguous identity</span>
          <strong>
            {overview.ambiguousIdentity === null
              ? "Unavailable"
              : overview.ambiguousIdentity
                ? "Yes"
                : "No"}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Anatomy extent</span>
          <strong>{(overview.anatomyExtent ?? "Unavailable").replaceAll("_", " ")}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Missing anatomy (roots/bone)</span>
          <strong>
            {overview.missingAnatomy === null
              ? "Unavailable"
              : overview.missingAnatomy
                ? "Yes — crown-only STL"
                : "No"}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Mesh watertight</span>
          <strong>
            {validation ? (validation.is_watertight ? "Yes" : "No") : "Unavailable"}
          </strong>
        </div>
      </section>
      </AdvancedDetails>

      <section className="analysis-section" aria-labelledby="analysis-review-findings">
        <h3 id="analysis-review-findings" className="eyebrow">
          Review Findings
        </h3>
        {findings.map((finding) => (
          <small
            key={`${finding.kind}-${finding.text}`}
            className={finding.kind === "note" ? "cad-review-note" : "diagnostic-warning"}
          >
            {finding.text}
          </small>
        ))}
      </section>
    </div>
  );
}

interface AnalysisInspectorProps {
  diagnostic: PipelineDiagnostic | null;
  dentalIntelligence?: CaseDentalIntelligencePayload | null;
  teeth: readonly ReviewToothMesh[];
  validation: MeshValidationResult | null;
  selectedLabel: string;
  selectedConfidence: number | null;
  selectedArch: string | null;
}

export function AnalysisInspector({
  diagnostic,
  dentalIntelligence = null,
  teeth,
  validation,
  selectedLabel,
  selectedConfidence,
  selectedArch,
}: AnalysisInspectorProps): JSX.Element {
  const overview = buildAnalysisOverview({ diagnostic, teeth, dentalIntelligence });
  const findings = buildAnalysisFindings({ diagnostic, validation, dentalIntelligence });

  return (
    <div className="cad-inspector-section" data-testid="analysis-inspector">
      <AdvancedDetails summary="Advanced details">
      <span className="eyebrow">Analysis</span>
      <h2>Data Quality</h2>
      <p>
        {diagnostic || dentalIntelligence
          ? "Anatomy overview uses reported instance counts only — no invented FDI or landmarks."
          : "Upload both arches and run Analyze case to review findings."}
      </p>
      <div className="cad-stat-row">
        <span>Tooth Identification</span>
        <strong>{overview.stateLabel}</strong>
      </div>
      {overview.overallTruthState && (
        <div className="cad-stat-row">
          <span>Intelligence truth</span>
          <strong>{formatTruthState(overview.overallTruthState)}</strong>
        </div>
      )}
      <div className="cad-stat-row">
        <span>Arch Analysis</span>
        <strong>{formatAvailability(overview.archAnalysisAvailable)}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Occlusion</span>
        <strong>
          {overview.occlusionTruth
            ? formatTruthState(overview.occlusionTruth)
            : formatOcclusionAvailability(overview.occlusionAvailability)}
        </strong>
      </div>
      <div className="cad-stat-row">
        <span>Landmarks</span>
        <strong>
          {overview.landmarksTruth
            ? formatTruthState(overview.landmarksTruth)
            : formatAvailability(overview.landmarksAvailable)}
        </strong>
      </div>
      <div className="cad-stat-row">
        <span>Clinical dental axes</span>
        <strong>
          {formatTruthState(
            overview.clinicalAxesTruth ??
              (overview.clinicalAxesAnatomyState as "not_available" | null) ??
              null,
          )}
        </strong>
      </div>
      <div className="cad-stat-row">
        <span>Treatment setup readiness</span>
        <strong>{formatTruthState(overview.treatmentSetupReadiness)}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Anatomy extent</span>
        <strong>{(overview.anatomyExtent ?? "Unavailable").replaceAll("_", " ")}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Measurements</span>
        <strong>{formatMeshMeasurement(validation)}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Selected tooth</span>
        <strong>{selectedLabel}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Arch</span>
        <strong>{selectedArch ?? "Unavailable"}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Confidence</span>
        <strong>
          {selectedConfidence === null ? "Unavailable" : selectedConfidence.toFixed(3)}
        </strong>
      </div>
      <div className="cad-stat-row">
        <span>Review Findings</span>
        <strong>{findings.length}</strong>
      </div>
      </AdvancedDetails>
    </div>
  );
}
