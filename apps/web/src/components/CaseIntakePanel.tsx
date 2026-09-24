import type { ProcessingStatus } from "../api/client";
import {
  buildArchStatuses,
  buildCaseIntakeReadiness,
  formatCaseStatus,
  formatIntakeProcessingState,
  formatIntakeUploadState,
  type IntakeUploadState,
} from "../caseIntake";

interface ArchUploadView {
  filename: string;
  size: number;
  state: IntakeUploadState;
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
}

/** Case Intake left tools — Master Plan v2.1 labels and capabilities. */
export function CaseIntakePanel({
  patientReference,
  onPatientReferenceChange,
  caseId,
  caseStatus,
  archUploads,
  fileInputKeys,
  scanImportDisabled,
  isBusy,
  bothArchesValid,
  backendTreatment,
  processingStatus,
  onCreateCase,
  onUpload,
  onRemoveMesh,
  onAnalyzeCase,
  onReviewTreatmentProposal,
}: CaseIntakePanelProps): JSX.Element {
  const arches = buildArchStatuses(archUploads);
  const readiness = buildCaseIntakeReadiness({
    hasCase: caseId !== null,
    upperState: archUploads.upper.state,
    lowerState: archUploads.lower.state,
  });
  const processing = formatIntakeProcessingState(processingStatus);

  return (
    <div className="case-intake-panel case-form" data-testid="case-intake-panel">
      <section className="case-intake-section" aria-labelledby="case-intake-new-case">
        <h3 id="case-intake-new-case" className="eyebrow">
          New Case
        </h3>
        <button
          className="primary-button"
          onClick={onCreateCase}
          disabled={isBusy}
          aria-label="Create case"
        >
          New Case
        </button>
      </section>

      <section className="case-intake-section" aria-labelledby="case-intake-information">
        <h3 id="case-intake-information" className="eyebrow">
          Case Information
        </h3>
        <label htmlFor="patient-reference">Patient reference</label>
        <input
          id="patient-reference"
          value={patientReference}
          onChange={(event) => onPatientReferenceChange(event.target.value)}
          placeholder="P-0001"
        />
        <div className="cad-stat-row">
          <span>Case identity</span>
          <strong>{caseId ?? "Not created"}</strong>
        </div>
      </section>

      <section className="case-intake-section" aria-labelledby="case-intake-scan-import">
        <h3 id="case-intake-scan-import" className="eyebrow">
          Scan Import
        </h3>
        {arches.map((arch) => {
          const upload = archUploads[arch.arch];
          return (
            <div className="mesh-upload" key={arch.arch}>
              <label htmlFor={`${arch.arch}-stl`}>{arch.label} STL</label>
              <input
                id={`${arch.arch}-stl`}
                key={fileInputKeys[arch.arch]}
                type="file"
                accept=".stl"
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
                    {(upload.size / 1024).toFixed(1)} KB · {upload.state}
                  </small>
                  <button
                    className="text-button"
                    onClick={() => onRemoveMesh(arch.arch)}
                    disabled={isBusy || backendTreatment}
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </section>

      <section className="case-intake-section" aria-labelledby="case-intake-data-readiness">
        <h3 id="case-intake-data-readiness" className="eyebrow">
          Data Readiness
        </h3>
        <div className="cad-stat-row">
          <span>Completeness</span>
          <strong>{readiness.completenessLabel}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Upper Arch</span>
          <strong>{formatIntakeUploadState(archUploads.upper.state)}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Lower Arch</span>
          <strong>{formatIntakeUploadState(archUploads.lower.state)}</strong>
        </div>
      </section>

      <section className="case-intake-section" aria-labelledby="case-intake-case-status">
        <h3 id="case-intake-case-status" className="eyebrow">
          Case Status
        </h3>
        <div className="cad-stat-row">
          <span>Case Status</span>
          <strong>{formatCaseStatus(caseStatus)}</strong>
        </div>
        <div className="cad-stat-row">
          <span>Processing state</span>
          <strong>{processing.label}</strong>
        </div>
        {processing.detail ? <small className="cad-review-note">{processing.detail}</small> : null}
      </section>

      <section className="case-intake-section" aria-labelledby="case-intake-next-actions">
        <h3 id="case-intake-next-actions" className="eyebrow">
          Next actions
        </h3>
        <button
          aria-label="Review segmentation"
          className="secondary-button"
          onClick={onAnalyzeCase}
          disabled={!bothArchesValid}
        >
          Analyze case
        </button>
        <button
          aria-label="Generate Treatment Setup"
          className="primary-button"
          onClick={onReviewTreatmentProposal}
          disabled={!bothArchesValid || backendTreatment}
        >
          Review Treatment Setup
        </button>
      </section>
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
      <span className="eyebrow">Case Intake</span>
      <h2>{caseId ? "Data Readiness" : "New Case"}</h2>
      <p>Import Upper Arch and Lower Arch STL scans to establish the dental scene.</p>
      <div className="cad-stat-row">
        <span>Case Information</span>
        <strong>{patientReference || "—"}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Case identity</span>
        <strong>{caseId ?? "Not created"}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Upper Arch</span>
        <strong>{formatIntakeUploadState(archUploads.upper.state)}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Lower Arch</span>
        <strong>{formatIntakeUploadState(archUploads.lower.state)}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Data Readiness</span>
        <strong>{readiness.completenessLabel}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Case Status</span>
        <strong>{formatCaseStatus(caseStatus)}</strong>
      </div>
      <div className="cad-stat-row">
        <span>Processing state</span>
        <strong>{processing.label}</strong>
      </div>
      {processing.detail ? <small className="cad-review-note">{processing.detail}</small> : null}
    </div>
  );
}
