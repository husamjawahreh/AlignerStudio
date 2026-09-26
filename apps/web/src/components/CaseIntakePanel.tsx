import type { IntakeArtifact, PreparationJob, SegmentationJob, SegmentationState } from "@alignerstudio/contracts";
import type { ProcessingStatus } from "../api/client";
import {
  buildArchStatuses,
  buildCaseIntakeReadiness,
  formatCaseStatus,
  formatIntakeProcessingState,
  formatIntakeUploadState,
  type IntakeUploadState,
} from "../caseIntake";
import {
  ScanPreparationForm,
  type PreparationPreview,
  type PreparationRequest,
} from "./ScanPreparationForm";
import {
  SegmentationReviewForm,
  type SegmentationReviewRequest,
} from "./SegmentationReviewForm";

interface ArchUploadView {
  filename: string;
  size: number;
  state: IntakeUploadState;
  validation?: { triangle_count: number; is_watertight: boolean; errors: string[] } | null;
  intake?: IntakeArtifact | null;
}

interface CaseIntakePanelProps {
  patientReference: string;
  onPatientReferenceChange: (value: string) => void;
  caseId: string | null;
  caseStatus: string | null;
  archUploads: { upper: ArchUploadView; lower: ArchUploadView };
  fileInputKeys: { upper: number; lower: number };
  scanImportDisabled: boolean;
  isBusy: boolean;
  bothArchesValid: boolean;
  backendTreatment: boolean;
  processingStatus: ProcessingStatus | null;
  onCreateCase: () => void;
  onUpload: (arch: "upper" | "lower", file: File) => void;
  onRemoveMesh: (arch: "upper" | "lower") => void;
  onAnalyzeCase: () => void;
  onReviewTreatmentProposal: () => void;
  /** Open a stored plan. Does not start processing. */
  onOpenTreatmentPlan?: () => void;
  onRequestNewCase?: () => void;
  /** When tooth instances already exist, the plan action becomes the primary next step. */
  segmentationReviewed?: boolean;
  /** Wave 5 resolver id. When set, only that action uses the primary button. */
  primaryActionId?: string | null;
  preparationPreview?: { arch: "upper" | "lower"; body: PreparationPreview } | null;
  preparationJob?: { arch: "upper" | "lower"; job: PreparationJob } | null;
  onPrepare?: (arch: "upper" | "lower", request: PreparationRequest) => void;
  onDismissPreview?: () => void;
  onCancelPreparationJob?: () => void;
  segmentationJob?: { arch: "upper" | "lower"; job: SegmentationJob } | null;
  onStartSegmentation?: (arch: "upper" | "lower") => void;
  onReviewSegmentation?: (arch: "upper" | "lower", request: SegmentationReviewRequest) => void;
}

/** Case Intake — creation flow before case; active-case workspace after creation. */
export function CaseIntakePanel({
  patientReference,
  onPatientReferenceChange,
  caseId,
  archUploads,
  fileInputKeys,
  scanImportDisabled,
  isBusy,
  bothArchesValid,
  backendTreatment,
  onCreateCase,
  onUpload,
  onRemoveMesh,
  onAnalyzeCase,
  onReviewTreatmentProposal,
  onOpenTreatmentPlan,
  onRequestNewCase,
  segmentationReviewed = false,
  primaryActionId = null,
  preparationPreview = null,
  preparationJob = null,
  onPrepare,
  onDismissPreview,
  onCancelPreparationJob,
  segmentationJob = null,
  onStartSegmentation,
  onReviewSegmentation,
}: CaseIntakePanelProps): JSX.Element {
  const arches = buildArchStatuses(archUploads);
  const hasCase = caseId !== null;

  return (
    <div
      className={`case-intake-panel case-form ${hasCase ? "is-active-case" : "is-new-case"}`}
      data-testid="case-intake-panel"
      data-case-state={hasCase ? "active" : "create"}
    >
      {!hasCase ? (
        <section className="case-intake-section" aria-labelledby="case-intake-create">
          <h3 id="case-intake-create" className="eyebrow">
            New Case
          </h3>
          <p className="cad-review-note">Create a case, then import one or both arches.</p>
          <label htmlFor="patient-reference">Patient reference</label>
          <input
            id="patient-reference"
            value={patientReference}
            onChange={(event) => onPatientReferenceChange(event.target.value)}
            placeholder="P-0001"
          />
          <button
            className="primary-button"
            onClick={onCreateCase}
            disabled={isBusy}
            aria-label="Create case"
            data-testid="create-case-primary"
          >
            Create Case
          </button>
        </section>
      ) : (
        <section className="case-intake-section" aria-labelledby="case-intake-active">
          <h3 id="case-intake-active" className="eyebrow">
            Active Case
          </h3>
          <div className="cad-stat-row">
            <span>Patient</span>
            <strong>{patientReference || "—"}</strong>
          </div>
          <div className="cad-stat-row">
            <span>Case</span>
            <strong data-testid="active-case-id">{caseId}</strong>
          </div>
          {onRequestNewCase ? (
            <button
              className="text-button"
              onClick={onRequestNewCase}
              disabled={isBusy}
              data-testid="secondary-new-case"
            >
              Start another case…
            </button>
          ) : null}
        </section>
      )}

      <section className="case-intake-section" aria-labelledby="case-intake-scan-import">
        <h3 id="case-intake-scan-import" className="eyebrow">
          Scan Import
        </h3>
        <p className="cad-review-note" data-testid="crown-stl-limitation">
          STL, PLY, or OBJ. One arch is enough. A second arch does not establish bite, contact, or occlusion.
          Roots and FDI are not read from these files.
        </p>
        {arches.map((arch) => {
          const upload = archUploads[arch.arch];
          const validation = upload.validation;
          return (
            <div className="mesh-upload" key={arch.arch}>
              <label htmlFor={`${arch.arch}-stl`}>{arch.label} scan</label>
              <input
                id={`${arch.arch}-stl`}
                key={fileInputKeys[arch.arch]}
                type="file"
                accept=".stl,.ply,.obj"
                disabled={scanImportDisabled}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) onUpload(arch.arch, file);
                }}
              />
              {upload.state !== "empty" && (
                <div className={`mesh-upload-status ${upload.state}`}>
                  <span>{upload.filename}</span>
                  <small>
                    {(upload.size / 1024).toFixed(1)} KB · {formatIntakeUploadState(upload.state)}
                  </small>
                  <button
                    className="text-button"
                    onClick={() => onRemoveMesh(arch.arch)}
                    disabled={isBusy || backendTreatment}
                  >
                    Remove
                  </button>
                  <details className="intake-file-details">
                    <summary>File details</summary>
                    <small data-testid={`${arch.arch}-intake-quality`}>
                      {upload.intake
                        ? `${upload.intake.format ?? "mesh"} · ${upload.intake.vertex_count ?? "?"} vertices · ${upload.intake.face_count ?? "?"} faces · ${upload.intake.readiness ?? "unmeasured"}`
                        : validation
                          ? `${validation.triangle_count} triangles · ${validation.is_watertight ? "closed mesh" : "not watertight"}`
                          : "Mesh quality is not available yet."}
                      {upload.intake?.arch?.truth ? ` · arch ${upload.intake.arch.truth}` : ""}
                      {" "}
                      A content hash is kept with the stored upload and is not repeated here.
                    </small>
                    {upload.intake?.warnings?.length ? (
                      <small>{upload.intake.warnings.join(", ")}</small>
                    ) : null}
                    {upload.intake ? (
                      <small>Occlusion is not inferred. FDI is not assigned.</small>
                    ) : null}
                    {upload.intake && onPrepare && onDismissPreview ? (
                      <ScanPreparationForm
                        arch={arch.arch}
                        preparation={upload.intake.preparation}
                        sourceVertexCount={upload.intake.vertex_count}
                        sourceFaceCount={upload.intake.face_count}
                        preview={
                          preparationPreview?.arch === arch.arch ? preparationPreview.body : null
                        }
                        activeJob={preparationJob?.arch === arch.arch ? preparationJob.job : null}
                        disabled={isBusy}
                        onPrepare={onPrepare}
                        onDismissPreview={onDismissPreview}
                        onCancelJob={onCancelPreparationJob}
                      />
                    ) : null}
                    {upload.intake?.preparation && onStartSegmentation && onReviewSegmentation ? (
                      <SegmentationReviewForm
                        arch={arch.arch}
                        readiness={upload.intake.preparation.readiness}
                        segmentation={upload.intake.segmentation as SegmentationState | null | undefined}
                        job={segmentationJob?.arch === arch.arch ? segmentationJob.job : null}
                        disabled={isBusy}
                        onStart={() => onStartSegmentation(arch.arch)}
                        onReview={(request) => onReviewSegmentation(arch.arch, request)}
                      />
                    ) : null}
                    {validation?.errors.length ? (
                      <small>{validation.errors.join(" ")}</small>
                    ) : null}
                  </details>
                </div>
              )}
            </div>
          );
        })}
      </section>

      {hasCase && (
        <section className="case-intake-section" aria-labelledby="case-intake-next-actions">
          <h3 id="case-intake-next-actions" className="eyebrow">
            Next
          </h3>
          <button
            aria-label="Review segmentation"
            className={
              primaryActionId
                ? primaryActionId === "review-segmentation" || primaryActionId === "retry-segmentation"
                  ? "primary-button"
                  : "secondary-button"
                : segmentationReviewed
                  ? "secondary-button"
                  : "primary-button"
            }
            onClick={onAnalyzeCase}
            disabled={!bothArchesValid}
            data-testid={
              primaryActionId
                ? primaryActionId === "review-segmentation" || primaryActionId === "retry-segmentation"
                  ? "primary-next-action"
                  : undefined
                : segmentationReviewed
                  ? undefined
                  : "primary-next-action"
            }
            title="Run segmentation review for the imported scans. This does not assign clinical FDI."
          >
            {primaryActionId === "retry-segmentation" ? "Retry segmentation" : "Analyze case"}
          </button>
          <button
            aria-label={backendTreatment ? "Open Treatment Plan" : "Generate Treatment Setup"}
            className={
              primaryActionId
                ? (backendTreatment
                    ? primaryActionId === "open-treatment-plan"
                    : primaryActionId === "create-treatment-plan")
                  ? "primary-button"
                  : "secondary-button"
                : "secondary-button"
            }
            onClick={backendTreatment ? onOpenTreatmentPlan : onReviewTreatmentProposal}
            disabled={!bothArchesValid || isBusy || (backendTreatment && !onOpenTreatmentPlan)}
            data-testid={
              primaryActionId &&
              (backendTreatment
                ? primaryActionId === "open-treatment-plan"
                : primaryActionId === "create-treatment-plan")
                ? "primary-next-action"
                : undefined
            }
            title={
              backendTreatment
                ? "Opens the stored treatment plan. This does not rebuild it."
                : "Creates a treatment plan. This does not run by itself when you open treatment setup."
            }
          >
            {backendTreatment ? "Open Treatment Plan" : "Create Treatment Plan"}
          </button>
        </section>
      )}
    </div>
  );
}

interface CaseIntakeInspectorProps {
  caseId: string | null;
  patientReference: string;
  caseStatus: string | null;
  archUploads: { upper: ArchUploadView; lower: ArchUploadView };
  processingStatus: ProcessingStatus | null;
}

/** Case Intake right inspector — identity, readiness, processing. */
export function CaseIntakeInspector({
  caseId,
  patientReference,
  caseStatus,
  archUploads,
  processingStatus,
}: CaseIntakeInspectorProps): JSX.Element {
  const readiness = buildCaseIntakeReadiness({
    hasCase: caseId !== null,
    upperState: archUploads.upper.state,
    lowerState: archUploads.lower.state,
  });
  const processing = formatIntakeProcessingState(processingStatus);

  return (
    <div className="cad-inspector-section" data-testid="case-intake-inspector">
      <span className="eyebrow">Case</span>
      <h2>{caseId ? "Active case" : "Create a case"}</h2>
      <p>
        {caseId
          ? "Import upper and lower scans, then continue to Analysis."
          : "Create a case to begin scan import and clinical review."}
      </p>
      <div className="cad-stat-row">
        <span>Patient</span>
        <strong>{patientReference || "—"}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Case</span>
        <strong>{caseId ?? "Not created"}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Upper</span>
        <strong>{formatIntakeUploadState(archUploads.upper.state)}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Lower</span>
        <strong>{formatIntakeUploadState(archUploads.lower.state)}</strong>
      </div>
      <div className="cad-stat-row" data-readiness-surface="primary" data-testid="case-readiness-home">
        <span>Readiness</span>
        <strong>{readiness.completenessLabel}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Case status</span>
        <strong>{formatCaseStatus(caseStatus)}</strong>
      </div>
      {processing.detail && processing.label !== "Idle" ? (
        <small className="cad-review-note">Processing is reported in the status line.</small>
      ) : null}
    </div>
  );
}
