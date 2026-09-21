import { useEffect, useMemo, useState } from "react";
import type { Case, MeshValidationResult } from "@alignerstudio/contracts";
import { api, type PipelineDiagnostic } from "../api/client";
import { ExportPanel } from "../components/ExportPanel";
import { FixtureBadge } from "../components/FixtureBadge";
import { InspectionPanel } from "../components/InspectionPanel";
import { ProposalPanels } from "../components/ProposalPanels";
import { StageTimeline } from "../components/StageTimeline";
import { UnavailableState } from "../components/UnavailableState";
import { ValidationPanel } from "../components/ValidationPanel";
import { engineeringFixtureBundle } from "../review/fixtureData";
import {
  applyFixtureMovementEdit,
  cancelFixtureEdits,
  cloneMovement,
  hasMovementChanges,
  recalculateFixtureBundle,
  resetAllFixtureEdits,
  resetFixtureTooth,
} from "../review/editing";
import {
  modifyIPRAmount,
  resetAdjunctProposals,
  setAttachmentStatus,
  setIPRStatus,
} from "../review/proposalEditing";
import type { MovementSummary, ReviewBundle } from "../review/types";
import { StageViewer } from "../viewer/StageViewer";

const WORKFLOW = [
  "Case",
  "Analysis",
  "Treatment Plan",
  "Stage Review",
  "Tooth Inspection",
  "Validation",
] as const;

type Arch = "upper" | "lower";
type UploadState = "empty" | "uploading" | "valid" | "invalid" | "error";

interface ArchUpload {
  filename: string;
  size: number;
  state: UploadState;
  validation: MeshValidationResult | null;
}

const EMPTY_UPLOAD: ArchUpload = { filename: "", size: 0, state: "empty", validation: null };

function unavailableReviewBundle(reason: string): ReviewBundle {
  return {
    stages: [],
    provenance: "generated",
    fixture: false,
    realDataAvailable: false,
    unavailableReason: reason,
    proposalKind: "original_generated",
    editHistory: [],
    iprSites: [],
    attachmentSites: [],
  };
}

export function App(): JSX.Element {
  const [patientReference, setPatientReference] = useState("");
  const [activeCase, setActiveCase] = useState<Case | null>(null);
  const [validation, setValidation] = useState<MeshValidationResult | null>(null);
  const [archUploads, setArchUploads] = useState<Record<Arch, ArchUpload>>({
    upper: EMPTY_UPLOAD,
    lower: EMPTY_UPLOAD,
  });
  const [fileInputKeys, setFileInputKeys] = useState<Record<Arch, number>>({ upper: 0, lower: 0 });
  const [pipelineDiagnostic, setPipelineDiagnostic] = useState<PipelineDiagnostic | null>(null);
  const [backendTreatment, setBackendTreatment] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [selectedTooth, setSelectedTooth] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showUpper, setShowUpper] = useState(true);
  const [showLower, setShowLower] = useState(true);
  const [showOriginal, setShowOriginal] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const [reviewBundle, setReviewBundle] = useState<ReviewBundle>(() =>
    unavailableReviewBundle(
      "Treatment plan unavailable. Load the engineering demo or create a case.",
    ),
  );
  const [draftMovement, setDraftMovement] = useState<MovementSummary | null>(null);
  const [recalculationState, setRecalculationState] = useState<
    "idle" | "recalculating" | "complete"
  >("idle");

  const fixtureStage = reviewBundle.stages[stageIndex] ?? null;
  const selectedFixtureTooth = useMemo(
    () => fixtureStage?.teeth.find((tooth) => tooth.fdiNumber === selectedTooth) ?? null,
    [fixtureStage, selectedTooth],
  );
  const originalTooth =
    selectedTooth === null
      ? null
      : (engineeringFixtureBundle.stages
          .at(-1)
          ?.teeth.find((tooth) => tooth.fdiNumber === selectedTooth) ?? null);
  const currentProposalTooth =
    selectedTooth === null
      ? null
      : (reviewBundle.stages.at(-1)?.teeth.find((tooth) => tooth.fdiNumber === selectedTooth) ??
        null);
  const bothArchesValid =
    archUploads.upper.state === "valid" && archUploads.lower.state === "valid";
  const treatmentAvailable = reviewBundle.realDataAvailable && fixtureStage !== null;

  function clearRealCaseReview(reason: string): void {
    setReviewBundle(unavailableReviewBundle(reason));
    setStageIndex(0);
    setSelectedTooth(null);
    setDraftMovement(null);
    setRecalculationState("idle");
    setExportMessage(null);
  }

  useEffect(() => {
    if (!isPlaying) return;
    const timer = window.setInterval(() => {
      setStageIndex((current) => {
        if (current >= reviewBundle.stages.length - 1) {
          setIsPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 900);
    return () => window.clearInterval(timer);
  }, [isPlaying, reviewBundle.stages.length]);

  function handleSelectTooth(toothNumber: number): void {
    setSelectedTooth(toothNumber);
    const tooth = reviewBundle.stages.at(-1)?.teeth.find((item) => item.fdiNumber === toothNumber);
    setDraftMovement(tooth ? cloneMovement(tooth.movement) : null);
  }

  async function handleApplyEdit(): Promise<void> {
    if (selectedTooth === null || !draftMovement) return;
    if (backendTreatment && activeCase) {
      setIsBusy(true);
      try {
        setReviewBundle(await api.applyTreatmentEdit(activeCase.id, selectedTooth, draftMovement));
        setRecalculationState("idle");
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setIsBusy(false);
      }
      return;
    }
    setReviewBundle((current) =>
      applyFixtureMovementEdit(current, selectedTooth, draftMovement, new Date().toISOString()),
    );
    setRecalculationState("idle");
  }

  function handleCancelEdit(): void {
    setReviewBundle((current) => cancelFixtureEdits(current));
    setDraftMovement(currentProposalTooth ? cloneMovement(currentProposalTooth.movement) : null);
  }

  function handleResetTooth(): void {
    if (selectedTooth === null) return;
    const next = resetFixtureTooth(reviewBundle, selectedTooth, new Date().toISOString());
    setReviewBundle(next);
    setDraftMovement(originalTooth ? cloneMovement(originalTooth.movement) : null);
  }

  function handleResetAll(): void {
    const next = resetAllFixtureEdits(reviewBundle, new Date().toISOString());
    setReviewBundle(next);
    setDraftMovement(originalTooth ? cloneMovement(originalTooth.movement) : null);
  }

  async function handleRecalculate(): Promise<void> {
    if (backendTreatment && activeCase) {
      setRecalculationState("recalculating");
      try {
        setReviewBundle(await api.recalculateTreatment(activeCase.id));
        setStageIndex(0);
        setRecalculationState("complete");
      } catch (err) {
        setError((err as Error).message);
        setRecalculationState("idle");
      }
      return;
    }
    setRecalculationState("recalculating");
    window.setTimeout(() => {
      setReviewBundle((current) => recalculateFixtureBundle(current));
      setRecalculationState("complete");
      setStageIndex(0);
    }, 250);
  }

  async function handleExportRequest(): Promise<void> {
    if (!backendTreatment || !activeCase) {
      setExportMessage(
        "Export requires an API-backed treatment session; local fixture mode cannot export.",
      );
      return;
    }
    setExportMessage(null);
    try {
      const download = await api.exportTreatment(activeCase.id);
      const link = document.createElement("a");
      link.href = URL.createObjectURL(download.blob);
      link.download = download.filename;
      link.click();
      URL.revokeObjectURL(link.href);
      setExportMessage(
        `Export complete. Manifest ${String(download.manifest?.manifest_hash ?? "metadata unavailable")}.`,
      );
    } catch (err) {
      setExportMessage((err as Error).message);
    }
  }

  async function handleLoadEngineeringDemo(): Promise<void> {
    setError(null);
    setIsBusy(true);
    try {
      const demo = await api.createEngineeringDemo();
      setActiveCase(demo.case);
      setReviewBundle(demo.review_bundle);
      setBackendTreatment(true);
      setStageIndex(0);
      setValidation(null);
      setArchUploads({ upper: EMPTY_UPLOAD, lower: EMPTY_UPLOAD });
      setPipelineDiagnostic(null);
      setSelectedTooth(null);
      setDraftMovement(null);
      setRecalculationState("idle");
      setExportMessage(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleCreateCase(): Promise<void> {
    setError(null);
    setIsBusy(true);
    try {
      const created = await api.createCase(patientReference);
      setActiveCase(created);
      setValidation(null);
      setPipelineDiagnostic(null);
      setArchUploads({ upper: EMPTY_UPLOAD, lower: EMPTY_UPLOAD });
      setBackendTreatment(false);
      clearRealCaseReview(
        "Treatment plan unavailable. Upload and validate both arch STL files to continue.",
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleUploadAndValidate(arch: Arch, file: File): Promise<void> {
    if (!activeCase) return;
    setError(null);
    setIsBusy(true);
    setBackendTreatment(false);
    clearRealCaseReview("Treatment plan unavailable. Real uploaded cases never use fixture data.");
    setArchUploads((current) => ({
      ...current,
      [arch]: { filename: file.name, size: file.size, state: "uploading", validation: null },
    }));
    try {
      const updated = await api.uploadMesh(activeCase.id, arch, file);
      setActiveCase(updated);
      const meshValidation = await api.validateMesh(activeCase.id, arch);
      setValidation(meshValidation);
      setArchUploads((current) => ({
        ...current,
        [arch]: {
          filename: file.name,
          size: file.size,
          state: meshValidation.is_valid ? "valid" : "invalid",
          validation: meshValidation,
        },
      }));
    } catch (err) {
      setError((err as Error).message);
      setArchUploads((current) => ({
        ...current,
        [arch]: { ...current[arch], state: "error" },
      }));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRemoveMesh(arch: Arch): Promise<void> {
    if (!activeCase) return;
    setError(null);
    setIsBusy(true);
    try {
      setActiveCase(await api.removeMesh(activeCase.id, arch));
      setArchUploads((current) => ({ ...current, [arch]: EMPTY_UPLOAD }));
      setFileInputKeys((current) => ({ ...current, [arch]: current[arch] + 1 }));
      setPipelineDiagnostic(null);
      clearRealCaseReview(
        "Treatment plan unavailable. Upload and validate both arch STL files to continue.",
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsBusy(false);
    }
  }

  async function handleGeneratePlan(): Promise<void> {
    if (!activeCase) return;
    setError(null);
    setIsBusy(true);
    try {
      const upperDiagnostic = await api.processPipeline(activeCase.id, "upper");
      const lowerDiagnostic = await api.processPipeline(activeCase.id, "lower");
      setPipelineDiagnostic(
        upperDiagnostic.state === "model_unavailable" ? upperDiagnostic : lowerDiagnostic,
      );
      if (
        upperDiagnostic.state !== "planning_ready" ||
        lowerDiagnostic.state !== "planning_ready"
      ) {
        const diagnostic =
          upperDiagnostic.state === "model_unavailable" ? upperDiagnostic : lowerDiagnostic;
        clearRealCaseReview(
          diagnostic.state === "model_unavailable"
            ? "Segmentation model unavailable. Planning cannot continue until a verified model is configured."
            : "Treatment plan unavailable. Planning cannot continue until the pipeline is ready.",
        );
        return;
      }
      await api.generatePlan(activeCase.id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <img src="/assets/AS-logo.png" alt="AlignerStudio orthodontic review workspace" />
        </div>
        <div className="topbar-case">
          <span className="eyebrow">Active case</span>
          <strong>{activeCase?.patient_reference || "No case loaded"}</strong>
        </div>
        <div className="topbar-status">
          <span className="status-dot warning" /> Review mode
        </div>
      </header>

      <nav className="workflow-bar" aria-label="Treatment workflow">
        {WORKFLOW.map((step, index) => (
          <div
            className={`workflow-step ${index < 3 ? "is-complete" : index === 3 ? "is-active" : ""}`}
            key={step}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            {step}
          </div>
        ))}
      </nav>

      <main className="review-workspace">
        <aside className="context-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">Case context</span>
              <h2>Review setup</h2>
            </div>
            <span className="panel-index">01</span>
          </div>
          <div className="case-form">
            <label htmlFor="patient-reference">Patient reference</label>
            <input
              id="patient-reference"
              value={patientReference}
              onChange={(event) => setPatientReference(event.target.value)}
              placeholder="P-0001"
            />
            <button className="primary-button" onClick={handleCreateCase} disabled={isBusy}>
              Create case
            </button>
            <button
              className="secondary-button"
              onClick={handleLoadEngineeringDemo}
              disabled={isBusy}
            >
              Load engineering demo
            </button>
            {(["upper", "lower"] as const).map((arch) => {
              const upload = archUploads[arch];
              return (
                <div className="mesh-upload" key={arch}>
                  <label htmlFor={`${arch}-stl`}>
                    {arch === "upper" ? "Upper" : "Lower"} arch STL
                  </label>
                  <input
                    id={`${arch}-stl`}
                    key={fileInputKeys[arch]}
                    type="file"
                    accept=".stl"
                    disabled={!activeCase || backendTreatment || isBusy}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void handleUploadAndValidate(arch, file);
                    }}
                  />
                  {upload.state !== "empty" && (
                    <div className={`mesh-upload-status ${upload.state}`}>
                      <span>{upload.filename}</span>
                      <small>
                        {(upload.size / 1024).toFixed(1)} KB · {upload.state}
                      </small>
                      {upload.validation && !upload.validation.is_valid && (
                        <small>{upload.validation.errors.join(" ")}</small>
                      )}
                      <button
                        className="text-button"
                        onClick={() => void handleRemoveMesh(arch)}
                        disabled={isBusy || backendTreatment}
                      >
                        Remove
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
            <button
              className="secondary-button"
              onClick={handleGeneratePlan}
              disabled={!bothArchesValid || backendTreatment || isBusy}
            >
              Generate plan
            </button>
          </div>
          {activeCase && (
            <div className="case-summary">
              <span>Case status</span>
              <strong>{activeCase.status.replaceAll("_", " ")}</strong>
              {validation && (
                <small>
                  {validation.triangle_count.toLocaleString()} triangles ·{" "}
                  {validation.is_valid ? "mesh valid" : "mesh invalid"}
                </small>
              )}
              {pipelineDiagnostic && (
                <small>
                  Pipeline {pipelineDiagnostic.state.replaceAll("_", " ")} ·{" "}
                  {pipelineDiagnostic.tooth_instance_count} instances
                </small>
              )}
            </div>
          )}
          {error && <div className="error-message">{error}</div>}
          <div className="context-divider" />
          <span className="eyebrow">Scene controls</span>
          <label className="toggle-row">
            <input
              type="checkbox"
              checked={showUpper}
              onChange={(event) => setShowUpper(event.target.checked)}
            />
            <span>Upper arch</span>
          </label>
          <label className="toggle-row">
            <input
              type="checkbox"
              checked={showLower}
              onChange={(event) => setShowLower(event.target.checked)}
            />
            <span>Lower arch</span>
          </label>
          <label className="toggle-row">
            <input
              type="checkbox"
              checked={showOriginal}
              onChange={(event) => setShowOriginal(event.target.checked)}
            />
            <span>Original reference</span>
          </label>
          <label className="toggle-row">
            <input
              type="checkbox"
              checked={wireframe}
              onChange={(event) => setWireframe(event.target.checked)}
            />
            <span>Wireframe debug</span>
          </label>
          <button
            className="secondary-button"
            onClick={handleResetAll}
            disabled={reviewBundle.editHistory.length === 0}
          >
            Reset all edits
          </button>
        </aside>

        <section className="main-review-column">
          <div className="review-header">
            <div>
              <span className="eyebrow">Treatment plan review</span>
              <h1>Stage visualization</h1>
              <p>Inspect staged geometry, tooth movement, and validation findings.</p>
              {treatmentAvailable && (
                <span className="proposal-kind">
                  {reviewBundle.proposalKind.replaceAll("_", " ")}
                </span>
              )}
            </div>
            <div className="review-header-actions">
              {treatmentAvailable && (
                <FixtureBadge
                  fixture={reviewBundle.fixture}
                  provenance={reviewBundle.provenance}
                  notes="Engineering preview only"
                />
              )}
              <button
                className="primary-button recalculate-button"
                onClick={handleRecalculate}
                disabled={!treatmentAvailable || recalculationState === "recalculating"}
              >
                {recalculationState === "recalculating" ? "Recalculating…" : "Recalculate Plan"}
              </button>
            </div>
          </div>
          {!treatmentAvailable && (
            <UnavailableState
              title={
                pipelineDiagnostic?.state === "model_unavailable"
                  ? "Segmentation model unavailable"
                  : "Treatment plan unavailable"
              }
              message={
                reviewBundle.unavailableReason ??
                "The current case does not have staged treatment data."
              }
            />
          )}
          {treatmentAvailable && (
            <>
              <div className="viewer-card">
                <div className="viewer-card-header">
                  <span>3D scene · Stage {fixtureStage.index}</span>
                  <span className="scene-source">API engineering fixture</span>
                </div>
                <StageViewer
                  stage={fixtureStage}
                  selectedTooth={selectedTooth}
                  showUpper={showUpper}
                  showLower={showLower}
                  showOriginal={showOriginal}
                  wireframe={wireframe}
                  onSelectTooth={handleSelectTooth}
                  onFit={() => undefined}
                  onReset={() => undefined}
                />
              </div>
              <ValidationPanel stage={fixtureStage} />
              <ProposalPanels
                iprSites={reviewBundle.iprSites}
                attachmentSites={reviewBundle.attachmentSites}
                onIPRStatus={(siteId, status) =>
                  setReviewBundle((current) => setIPRStatus(current, siteId, status))
                }
                onIPRAmount={(siteId, amount) =>
                  setReviewBundle((current) => modifyIPRAmount(current, siteId, amount))
                }
                onAttachmentStatus={(siteId, status) =>
                  setReviewBundle((current) => setAttachmentStatus(current, siteId, status))
                }
                onReset={() => setReviewBundle((current) => resetAdjunctProposals(current))}
                readOnly={backendTreatment}
              />
              <ExportPanel bundle={reviewBundle} onExport={() => void handleExportRequest()} />
            </>
          )}
          {exportMessage && <div className="recalculation-message">{exportMessage}</div>}
          {recalculationState === "complete" && (
            <div className="recalculation-message">
              Recalculated fixture plan and validation state are ready for review.
            </div>
          )}
          {treatmentAvailable && (
            <StageTimeline
              stages={reviewBundle.stages}
              selectedIndex={stageIndex}
              isPlaying={isPlaying}
              onSelect={(index) => {
                setStageIndex(index);
                setIsPlaying(false);
              }}
              onPrevious={() => setStageIndex((index) => Math.max(0, index - 1))}
              onNext={() =>
                setStageIndex((index) => Math.min(reviewBundle.stages.length - 1, index + 1))
              }
              onTogglePlay={() => setIsPlaying((playing) => !playing)}
            />
          )}
        </section>

        <InspectionPanel
          tooth={selectedFixtureTooth}
          draftMovement={treatmentAvailable ? draftMovement : null}
          originalMovement={originalTooth?.movement ?? null}
          isDirty={
            draftMovement !== null &&
            currentProposalTooth !== null &&
            hasMovementChanges(draftMovement, currentProposalTooth.movement)
          }
          onDraftChange={setDraftMovement}
          onApply={() => void handleApplyEdit()}
          onCancel={handleCancelEdit}
          onReset={handleResetTooth}
        />
      </main>
    </div>
  );
}
