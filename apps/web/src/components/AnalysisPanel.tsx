import type { CaseDentalIntelligencePayload, MeshValidationResult } from "@alignerstudio/contracts";
import type { PipelineDiagnostic } from "../api/client";
import type { ReviewToothMesh } from "../review/types";
import {
  buildAnalysisFindings,
  buildAnalysisOverview,
  formatAvailability,
  formatMeshMeasurement,
  formatOcclusionAvailability,
  formatToothIdentity,
  formatTruthState,
} from "../analysisPresentation";

interface AnalysisPanelProps {
  bothArchesValid: boolean;
  diagnostic: PipelineDiagnostic | null;
  dentalIntelligence?: CaseDentalIntelligencePayload | null;
  teeth: readonly ReviewToothMesh[];
  validation: MeshValidationResult | null;
  hiddenToothIds: ReadonlySet<number>;
  onAnalyzeCase: () => void;
  onToggleToothVisibility: (instanceId: number) => void;
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
}: AnalysisPanelProps): JSX.Element {
  const overview = buildAnalysisOverview({ diagnostic, teeth, dentalIntelligence });
  const findings = buildAnalysisFindings({ diagnostic, validation, dentalIntelligence });

  return (
    <div className="analysis-panel case-form" data-testid="analysis-panel">
      <section className="analysis-section" aria-labelledby="analysis-run">
        <h3 id="analysis-run" className="eyebrow">
          Analysis
        </h3>
        <button
          aria-label="Review segmentation"
          className="primary-button"
          onClick={onAnalyzeCase}
          disabled={!bothArchesValid}
        >
          Analyze case
        </button>
        <div className="cad-stat-row">
          <span>State</span>
          <strong>{overview.stateLabel}</strong>
        </div>
        {overview.overallTruthState && (
          <div className="cad-stat-row">
            <span>Intelligence truth</span>
            <strong data-testid="intelligence-overall-truth">
              {formatTruthState(overview.overallTruthState)}
            </strong>
          </div>
        )}
      </section>

      <section className="analysis-section" aria-labelledby="analysis-tooth-id">
        <h3 id="analysis-tooth-id" className="eyebrow">
          Tooth Identification
        </h3>
        <div className="cad-stat-row">
          <span>Identified</span>
          <strong>
            {overview.identifiedTeeth === null ? "Unavailable" : overview.identifiedTeeth}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Uncertain</span>
          <strong>
            {overview.uncertainTeeth === null ? "Unavailable" : overview.uncertainTeeth}
          </strong>
        </div>
        <div className="cad-stat-row">
          <span>Unidentified</span>
          <strong>
            {overview.unidentifiedTeeth === null ? "Unavailable" : overview.unidentifiedTeeth}
          </strong>
        </div>
        {overview.identityReadiness && (
          <div className="cad-stat-row">
            <span>Identity readiness</span>
            <strong data-testid="identity-readiness">
              {formatTruthState(overview.identityReadiness)}
            </strong>
          </div>
        )}
        {teeth.length > 0 ? (
          <div className="cad-tooth-map" data-testid="toothinstancenet-summary">
            <strong>{teeth.length} visible meshes</strong>
            <small>Tooth identities from analysis only — FDI shown only when provided</small>
            {diagnostic?.fixture && import.meta.env.MODE === "test" && (
              <span className="production-test-metadata">
                Validated real-case fixture FIXTURE · not clinically valid
              </span>
            )}
            {diagnostic?.fixture && import.meta.env.MODE !== "test" && (
              <small>Requires Review — analysis identity is not clinical tooth numbering</small>
            )}
            {(diagnostic?.duplicate_fdi_numbers?.length ?? 0) > 0 && (
              <small className="diagnostic-warning">
                Duplicate FDI: {diagnostic?.duplicate_fdi_numbers?.join(", ")}
              </small>
            )}
            {(diagnostic?.missing_fdi_numbers?.length ?? 0) > 0 && (
              <small className="diagnostic-warning">
                Missing FDI: {diagnostic?.missing_fdi_numbers?.join(", ")}
              </small>
            )}
            {(diagnostic?.excluded_fragment_count ?? 0) > 0 && (
              <small>
                Excluded zero-face fragments: {diagnostic?.excluded_fragment_count}
              </small>
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
                    {formatToothIdentity(tooth)}
                    {fdiState ? ` · ${formatTruthState(fdiState)}` : ""}
                  </span>
                </label>
              );
            })}
          </div>
        ) : (
          <small className="cad-review-note">No tooth meshes available yet.</small>
        )}
      </section>

      <section className="analysis-section" aria-labelledby="analysis-arch">
        <h3 id="analysis-arch" className="eyebrow">
          Arch Analysis
        </h3>
        <div className="cad-stat-row">
          <span>Upper Arch meshes</span>
          <strong>{overview.upperCount}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Lower Arch meshes</span>
          <strong>{overview.lowerCount}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Arch analysis</span>
          <strong>{formatAvailability(overview.archAnalysisAvailable)}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Arch orientation</span>
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
        <div className="cad-stat-row">
          <span>Inter-tooth distances</span>
          <strong>
            {overview.interToothCount === null ? "Unavailable" : overview.interToothCount}
          </strong>
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
        <small className="cad-review-note">
          Occlusion stays unavailable until genuine registration or bite evidence exists.
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
            {overview.clinicalAxesTruth
              ? formatTruthState(overview.clinicalAxesTruth)
              : formatAvailability(overview.localAxesAvailable)}
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
          {overview.clinicalAxesTruth
            ? formatTruthState(overview.clinicalAxesTruth)
            : formatAvailability(overview.localAxesAvailable)}
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
    </div>
  );
}
