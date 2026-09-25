import { useEffect, useMemo, useState } from "react";
import type { Case, MeshValidationResult } from "@alignerstudio/contracts";
import { createSceneLayerRegistry } from "@alignerstudio/types";
import { api, type PipelineDiagnostic, type ProcessingStatus } from "../api/client";
import { ExportPanel } from "../components/ExportPanel";
import { AnalysisInspector, AnalysisPanel } from "../components/AnalysisPanel";
import { CaseIntakeInspector, CaseIntakePanel } from "../components/CaseIntakePanel";
import { ProductionInspector, ProductionPanel } from "../components/ProductionPanel";
import { RefinementInspector, RefinementPanel } from "../components/RefinementPanel";
import { StagingInspector, StagingPanel } from "../components/StagingPanel";
import { TreatmentSetupInspector, TreatmentSetupPanel } from "../components/TreatmentSetupPanel";
import {
  ValidationWorkflowInspector,
  ValidationWorkflowPanel,
} from "../components/ValidationWorkflowPanel";
import { ContextualToothToolbar } from "../components/ContextualToothToolbar";
import { InspectionPanel } from "../components/InspectionPanel";
import { formatToothIdentity } from "../analysisPresentation";
import { ProposalPanels } from "../components/ProposalPanels";
import { StageTimeline } from "../components/StageTimeline";
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
import type {
  MovementSummary,
  ProposalStatus,
  ReviewBundle,
  ReviewStage,
  ReviewToothMesh,
} from "../review/types";
import { StageViewer } from "../viewer/StageViewer";
import { createDentalSceneGraph } from "../viewer/sceneGraph";
import { findToothByKey } from "../viewer/toothKey";
import { useToothSelection } from "../viewer/useToothSelection";
import {
  AppShell,
  BottomTimeline,
  LeftToolPanel,
  RightInspector,
  StatusBar,
  ViewerOverlay,
  WorkflowHeader,
  WorkspaceContainer,
} from "../components/workspace/WorkspacePrimitives";
import { buildWorkflowActions, buildWorkflowSteps, workflowLabel, workflowPlanToken, workflowStepIndex, type WorkflowStepId } from "../workflow";
import { CaseLoadingOverlay, ProductionEmptyState, StatusPill } from "../components/production/ProductionPrimitives";
import { resolveLoadingPresentation } from "../components/production/loadingPresentation";
import {
  readRememberedActiveCaseId,
  rememberActiveCaseId,
} from "../caseWorkspacePersistence";

type WorkspaceId = WorkflowStepId;

type Arch = "upper" | "lower";
type UploadState = "empty" | "uploading" | "valid" | "invalid" | "error";

interface ArchUpload {
  filename: string;
  size: number;
  state: UploadState;
  validation: MeshValidationResult | null;
}

interface EditSnapshot {
  before: ReviewBundle;
  tooth: string;
  beforeMovement: MovementSummary;
  afterMovement: MovementSummary;
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

function pipelineStage(diagnostic: PipelineDiagnostic | null): ReviewStage | null {
  const teeth = (diagnostic?.tooth_instances ?? [])
    .map<ReviewToothMesh>((tooth) => ({
      instanceId: tooth.instance_id,
      fdiNumber: tooth.fdi_number,
      toothRef: tooth.tooth_ref,
      semanticLabel: tooth.semantic_label,
      planningMode: tooth.planning_mode,
      arch: tooth.arch,
      confidence: tooth.confidence,
      vertices: tooth.vertices,
      faces: tooth.faces,
      centroid: tooth.centroid,
      landmarks: tooth.landmarks ?? null,
      coordinateSystem: tooth.coordinate_system ?? null,
      movementReferenceFrame: tooth.movement_reference_frame ?? tooth.coordinate_system ?? null,
      anatomyExtent: tooth.anatomy_extent ?? "crown_only_stl",
      identificationStatus: tooth.identification_status,
      movement: {
        translationX: 0,
        translationY: 0,
        translationZ: 0,
        rotation: 0,
        tip: 0,
        torque: 0,
        angulation: 0,
        intrusion: 0,
        extrusion: 0,
      },
      validationStatus: "pass",
      validationMessage: "Validated ToothInstanceNet geometry; no treatment validation was run.",
      provenance: tooth.provenance,
      fixture: tooth.fixture,
      experimental: tooth.experimental,
    }));
  if (!diagnostic || teeth.length === 0) return null;
  return {
    index: 0,
    stageId: "toothinstancenet-validation-stage",
    teeth,
    validationStatus: diagnostic.duplicate_fdi_numbers?.length || diagnostic.missing_fdi_numbers?.length ? "warning" : "pass",
    collisionCount: 0,
    proximityCount: 0,
    contactCount: 0,
    warnings: [
      ...(diagnostic.duplicate_fdi_numbers?.length ? [`Duplicate FDI: ${diagnostic.duplicate_fdi_numbers.join(", ")}`] : []),
      ...(diagnostic.missing_fdi_numbers?.length ? [`Missing FDI: ${diagnostic.missing_fdi_numbers.join(", ")}`] : []),
      ...(diagnostic.excluded_fragment_count ? [`Excluded zero-face fragments: ${diagnostic.excluded_fragment_count}`] : []),
    ],
    provenance: diagnostic.provenance ?? "experimental",
    fixture: diagnostic.fixture ?? false,
  };
}

function mergePipelineDiagnostics(
  upperDiagnostic: PipelineDiagnostic,
  lowerDiagnostic: PipelineDiagnostic,
): PipelineDiagnostic {
  const upperInstances = upperDiagnostic.tooth_instances ?? [];
  const lowerInstances = (lowerDiagnostic.tooth_instances ?? []).map((tooth) => ({
    ...tooth,
    instance_id: tooth.instance_id + upperInstances.length,
  }));
  return {
    ...lowerDiagnostic,
    tooth_instances: [...upperInstances, ...lowerInstances],
    tooth_instance_count: upperDiagnostic.tooth_instance_count + lowerDiagnostic.tooth_instance_count,
    identified_teeth: upperDiagnostic.identified_teeth + lowerDiagnostic.identified_teeth,
    uncertain_teeth: upperDiagnostic.uncertain_teeth + lowerDiagnostic.uncertain_teeth,
    unidentified_teeth: upperDiagnostic.unidentified_teeth + lowerDiagnostic.unidentified_teeth,
    arch_analysis_available:
      upperDiagnostic.arch_analysis_available || lowerDiagnostic.arch_analysis_available,
    arch_measurements: lowerDiagnostic.arch_measurements ?? upperDiagnostic.arch_measurements ?? null,
    anatomical_intelligence: mergeAnatomicalIntelligence(
      upperDiagnostic.anatomical_intelligence,
      lowerDiagnostic.anatomical_intelligence,
    ),
    duplicate_fdi_numbers: [
      ...(upperDiagnostic.duplicate_fdi_numbers ?? []),
      ...(lowerDiagnostic.duplicate_fdi_numbers ?? []),
    ],
    missing_fdi_numbers: [
      ...(upperDiagnostic.missing_fdi_numbers ?? []),
      ...(lowerDiagnostic.missing_fdi_numbers ?? []),
    ],
    excluded_fragment_count:
      (upperDiagnostic.excluded_fragment_count ?? 0) +
      (lowerDiagnostic.excluded_fragment_count ?? 0),
  };
}

function mergeAnatomicalIntelligence(
  upper: PipelineDiagnostic["anatomical_intelligence"],
  lower: PipelineDiagnostic["anatomical_intelligence"],
): PipelineDiagnostic["anatomical_intelligence"] {
  if (!upper && !lower) return null;
  if (!upper) return lower ?? null;
  if (!lower) return upper;
  return {
    anatomy_extent: "crown_only_stl",
    landmarks_available: upper.landmarks_available || lower.landmarks_available,
    local_axes_available: upper.local_axes_available || lower.local_axes_available,
    movement_frames_available: upper.movement_frames_available || lower.movement_frames_available,
    arch_orientation_available: upper.arch_orientation_available || lower.arch_orientation_available,
    arch_form_available: upper.arch_form_available || lower.arch_form_available,
    midline_available: upper.midline_available || lower.midline_available,
    occlusion: upper.occlusion.availability === "unavailable" ? upper.occlusion : lower.occlusion,
    data_quality: {
      ...lower.data_quality,
      incomplete_scans: upper.data_quality.incomplete_scans || lower.data_quality.incomplete_scans,
      missing_teeth: upper.data_quality.missing_teeth || lower.data_quality.missing_teeth,
      ambiguous_identity:
        upper.data_quality.ambiguous_identity || lower.data_quality.ambiguous_identity,
      incomplete_occlusion: true,
      missing_anatomy: true,
      anatomy_extent: "crown_only_stl",
      findings: [...upper.data_quality.findings, ...lower.data_quality.findings],
      requires_review: true,
    },
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
  const [busyActivity, setBusyActivity] = useState<string | null>(null);
  const [stageIndex, setStageIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showUpper, setShowUpper] = useState(true);
  const [showLower, setShowLower] = useState(true);
  const [showOriginal, setShowOriginal] = useState(false);
  const [showGingiva, setShowGingiva] = useState(true);
  const [showTargetGhost, setShowTargetGhost] = useState(true);
  const [showSegmentation, setShowSegmentation] = useState(true);
  const [showMovementVectors, setShowMovementVectors] = useState(true);
  const [originalScanBuffers, setOriginalScanBuffers] = useState<
    Partial<Record<Arch, ArrayBuffer>>
  >({});
  const [originalOpacity, setOriginalOpacity] = useState(0.3);
  const [wireframe, setWireframe] = useState(false);
  const [hiddenToothIds, setHiddenToothIds] = useState<ReadonlySet<number>>(new Set());
  const [reviewBundle, setReviewBundle] = useState<ReviewBundle>(() =>
    unavailableReviewBundle(
      "Case preparation in progress. Import both arches to begin.",
    ),
  );
  const [draftMovement, setDraftMovement] = useState<MovementSummary | null>(null);
  const [recalculationState, setRecalculationState] = useState<
    "idle" | "recalculating" | "complete"
  >("idle");
  const [workspace, setWorkspace] = useState<WorkspaceId>("case-intake");
  const [gizmoMode, setGizmoMode] = useState<"translate" | "rotate">("translate");
  const [undoStack, setUndoStack] = useState<EditSnapshot[]>([]);
  const [redoStack, setRedoStack] = useState<EditSnapshot[]>([]);
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus | null>(null);

  const fixtureStage = reviewBundle.stages[stageIndex] ?? null;
  const treatmentAvailable = reviewBundle.realDataAvailable && fixtureStage !== null;
  const pipelineReviewStage = useMemo(() => pipelineStage(pipelineDiagnostic), [pipelineDiagnostic]);
  const activeReviewStage = treatmentAvailable ? fixtureStage : pipelineReviewStage;
  const { selection, selectTooth, clearSelection } = useToothSelection(
    activeReviewStage?.teeth ?? [],
  );
  const selectedTooth = selection.selectedToothRef;
  const sceneLayers = useMemo(
    () =>
      createSceneLayerRegistry({
        "upper-teeth": { visible: showUpper, available: activeReviewStage !== null },
        "lower-teeth": { visible: showLower, available: activeReviewStage !== null },
        "gingiva-base": {
          visible: showGingiva,
          available: activeReviewStage !== null,
          reason: activeReviewStage
            ? "Presentation gingiva (real when available, otherwise synthetic envelope)."
            : "Awaiting tooth surfaces.",
        },
        "original-scan": {
          visible: showOriginal,
          available: Boolean(originalScanBuffers.upper || originalScanBuffers.lower),
        },
        segmentation: { visible: showSegmentation, available: pipelineReviewStage !== null },
        "current-stage": { visible: treatmentAvailable, available: treatmentAvailable },
        "proposed-setup": {
          visible: showTargetGhost && treatmentAvailable,
          available: treatmentAvailable,
          reason: treatmentAvailable
            ? "Target / proposed setup ghost overlay."
            : "Requires a treatment proposal.",
        },
        "tooth-labels": { visible: true, available: activeReviewStage !== null },
        "movement-vectors": {
          visible: showMovementVectors,
          available: treatmentAvailable,
          reason: treatmentAvailable
            ? "Remaining movement from current stage to target."
            : "Requires a treatment proposal.",
        },
      }),
    [activeReviewStage, originalScanBuffers, pipelineReviewStage, showGingiva, showLower, showMovementVectors, showOriginal, showSegmentation, showTargetGhost, showUpper, treatmentAvailable],
  );
  const targetStage = useMemo(
    () => (treatmentAvailable ? reviewBundle.stages.at(-1) ?? null : null),
    [reviewBundle.stages, treatmentAvailable],
  );
  const sceneGraph = useMemo(
    () => activeReviewStage
      ? createDentalSceneGraph(activeReviewStage, originalScanBuffers, sceneLayers)
      : null,
    [activeReviewStage, originalScanBuffers, sceneLayers],
  );
  const selectedFixtureTooth = useMemo(
    () => findToothByKey(activeReviewStage?.teeth, selectedTooth),
    [activeReviewStage, selectedTooth],
  );
  const originalTooth =
    selectedTooth === null
      ? null
      : findToothByKey(engineeringFixtureBundle.stages.at(-1)?.teeth, selectedTooth);
  const currentProposalTooth =
    selectedTooth === null
      ? null
      : findToothByKey(reviewBundle.stages.at(-1)?.teeth, selectedTooth);
  const bothArchesValid =
    archUploads.upper.state === "valid" && archUploads.lower.state === "valid";
  const workflowSteps = useMemo(() => buildWorkflowSteps({
    activeStep: workspace as WorkflowStepId,
    hasCase: activeCase !== null,
    bothArchesValid,
    hasSegmentation: pipelineReviewStage !== null,
    hasTreatment: treatmentAvailable,
    editCount: reviewBundle.editHistory.length,
    hasValidation: treatmentAvailable && activeReviewStage?.validationStatus !== "unavailable",
  }), [activeCase, activeReviewStage, bothArchesValid, pipelineReviewStage, reviewBundle.editHistory.length, treatmentAvailable, workspace]);
  function clearRealCaseReview(reason: string): void {
    setReviewBundle(unavailableReviewBundle(reason));
    setStageIndex(0);
    clearSelection();
    setHiddenToothIds(new Set());
    setOriginalScanBuffers({});
    setDraftMovement(null);
    setRecalculationState("idle");
    setExportMessage(null);
    setProcessingStatus(null);
    setBusyActivity(null);
    setIsBusy(false);
  }

  function startBusy(activity: string): void {
    setIsBusy(true);
    setBusyActivity(activity);
  }

  function stopBusy(): void {
    setIsBusy(false);
    setBusyActivity(null);
  }

  const loadingPresentation = useMemo(
    () =>
      resolveLoadingPresentation({
        processingStatus,
        isBusy,
        busyActivity,
        recalculationState,
      }),
    [busyActivity, isBusy, processingStatus, recalculationState],
  );

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

  useEffect(() => {
    rememberActiveCaseId(activeCase?.id ?? null);
  }, [activeCase?.id]);

  useEffect(() => {
    let cancelled = false;
    const rememberedId = readRememberedActiveCaseId();
    if (!rememberedId) return;
    void (async () => {
      try {
        const restored = await api.getCase(rememberedId);
        if (cancelled) return;
        setActiveCase(restored);
        const uploads: Record<Arch, ArchUpload> = {
          upper: EMPTY_UPLOAD,
          lower: EMPTY_UPLOAD,
        };
        for (const mesh of restored.meshes ?? []) {
          const arch = mesh.arch as Arch;
          if (arch !== "upper" && arch !== "lower") continue;
          uploads[arch] = {
            filename: mesh.original_filename,
            size: 0,
            state: "valid",
            validation: null,
          };
        }
        setArchUploads(uploads);
        try {
          const status = await api.getProcessingStatus(rememberedId);
          if (!cancelled && status) setProcessingStatus(status);
        } catch {
          // No processing status yet.
        }
        try {
          const bundle = await api.getTreatment(rememberedId);
          if (cancelled) return;
          setReviewBundle(bundle);
          setBackendTreatment(true);
          setWorkspace("treatment-setup");
        } catch {
          // Treatment not composed yet — case metadata alone is enough to continue intake.
        }
      } catch {
        rememberActiveCaseId(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const isProcessing = processingStatus?.stage_status === "PROCESSING";
    if (!activeCase || !isProcessing) return;
    const caseId = activeCase.id;
    let cancelled = false;
    const timer = window.setInterval(() => {
      void api.getProcessingStatus(caseId).then((status) => {
        if (cancelled) return;
        setProcessingStatus(status);
        if (status.stage_status === "COMPLETED") {
          setBusyActivity("Loading treatment proposal");
          void api.getTreatment(caseId).then((bundle) => {
            if (cancelled) return;
            setReviewBundle(bundle);
            setBackendTreatment(true);
            setStageIndex(0);
            setWorkspace("staging");
            stopBusy();
          }).catch((error: Error) => {
            if (cancelled) return;
            setError(error.message);
            stopBusy();
          });
        } else if (status.stage_status === "FAILED" || status.stage_status === "CANCELLED") {
          setError(status.user_message);
          stopBusy();
        }
      }).catch((error: Error) => {
        if (cancelled) return;
        setError(error.message);
        stopBusy();
      });
    }, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeCase, processingStatus?.stage_status]);

  function handleSelectTooth(toothNumber: string): void {
    selectTooth(toothNumber);
    const tooth =
      findToothByKey(reviewBundle.stages.at(-1)?.teeth, toothNumber) ??
      findToothByKey(activeReviewStage?.teeth, toothNumber);
    setDraftMovement(tooth ? cloneMovement(tooth.movement) : null);
  }

  function handleClearSelection(): void {
    clearSelection();
    setDraftMovement(null);
  }

  function handleGizmoMovement(movement: MovementSummary): void {
    if (!draftMovement || draftMovement.locked) return;
    const frame = selectedFixtureTooth?.coordinateSystem ?? selectedFixtureTooth?.movementReferenceFrame;
    let next: MovementSummary = {
      ...draftMovement,
      translationX: movement.translationX,
      translationY: movement.translationY,
      translationZ: movement.translationZ,
      rotation: movement.rotation,
      tip: movement.tip,
      torque: movement.torque,
      // Preserve intrusion/extrusion/angulation/lock flags from draft.
      angulation: draftMovement.angulation ?? 0,
      intrusion: draftMovement.intrusion,
      extrusion: draftMovement.extrusion,
    };
    if (frame) {
      const world = [movement.translationX, movement.translationY, movement.translationZ] as const;
      next = {
        ...next,
        translationX: dot3(world, frame.lateral_axis),
        translationY: dot3(world, frame.anterior_axis),
        translationZ: dot3(world, frame.vertical_axis),
        tip: movement.tip,
        torque: movement.torque,
        rotation: movement.rotation,
      };
    }
    setDraftMovement(next);
  }

  async function handleApplyEdit(): Promise<void> {
    if (selectedTooth === null || !draftMovement) return;
    const beforeMovement = currentProposalTooth?.movement ?? draftMovement;
    const snapshot: EditSnapshot = {
      before: reviewBundle,
      tooth: selectedTooth,
      beforeMovement: cloneMovement(beforeMovement),
      afterMovement: cloneMovement(draftMovement),
    };
    if (backendTreatment && activeCase) {
      startBusy("Applying tooth edit");
      setRecalculationState("recalculating");
      try {
        // API apply_edit runs Target → Staging → Validation before returning.
        setReviewBundle(await api.applyTreatmentEdit(activeCase.id, selectedTooth, draftMovement));
        setUndoStack((current) => [...current, snapshot]);
        setRedoStack([]);
        setRecalculationState("complete");
        setStageIndex(0);
      } catch (err) {
        setError((err as Error).message);
        setRecalculationState("idle");
      } finally {
        stopBusy();
      }
      return;
    }
    setReviewBundle((current) =>
      recalculateFixtureBundle(
        applyFixtureMovementEdit(current, selectedTooth, draftMovement, new Date().toISOString()),
      ),
    );
    setUndoStack((current) => [...current, snapshot]);
    setRedoStack([]);
    setRecalculationState("complete");
  }

  async function handleResetTooth(): Promise<void> {
    if (selectedTooth === null) return;
    if (backendTreatment && activeCase) {
      startBusy("Resetting tooth");
      setRecalculationState("recalculating");
      try {
        setReviewBundle(await api.resetTreatmentTooth(activeCase.id, selectedTooth));
        setRecalculationState("complete");
        setStageIndex(0);
      } catch (err) {
        setError((err as Error).message);
        setRecalculationState("idle");
      } finally {
        stopBusy();
      }
      return;
    }
    const next = recalculateFixtureBundle(
      resetFixtureTooth(reviewBundle, selectedTooth, new Date().toISOString()),
    );
    setReviewBundle(next);
    setDraftMovement(originalTooth ? cloneMovement(originalTooth.movement) : null);
    setRecalculationState("complete");
  }

  async function handleResetAll(): Promise<void> {
    if (backendTreatment && activeCase) {
      startBusy("Resetting all edits");
      setRecalculationState("recalculating");
      try {
        setReviewBundle(await api.resetAllTreatmentEdits(activeCase.id));
        setRecalculationState("complete");
        setStageIndex(0);
      } catch (err) {
        setError((err as Error).message);
        setRecalculationState("idle");
      } finally {
        stopBusy();
      }
      return;
    }
    const next = recalculateFixtureBundle(
      resetAllFixtureEdits(reviewBundle, new Date().toISOString()),
    );
    setReviewBundle(next);
    setDraftMovement(originalTooth ? cloneMovement(originalTooth.movement) : null);
    setRecalculationState("complete");
  }

  function dot3(
    vector: readonly [number, number, number],
    axis: readonly [number, number, number],
  ): number {
    return vector[0] * axis[0] + vector[1] * axis[1] + vector[2] * axis[2];
  }

  async function handleUndo(): Promise<void> {
    const snapshot = undoStack.at(-1);
    if (!snapshot) return;
    setUndoStack((current) => current.slice(0, -1));
    setRedoStack((current) => [...current, snapshot]);
    if (backendTreatment && activeCase) {
      setRecalculationState("recalculating");
      setReviewBundle(await api.applyTreatmentEdit(activeCase.id, snapshot.tooth, snapshot.beforeMovement));
      setRecalculationState("complete");
    } else {
      setReviewBundle(snapshot.before);
    }
    setDraftMovement(cloneMovement(snapshot.beforeMovement));
  }

  async function handleRedo(): Promise<void> {
    const snapshot = redoStack.at(-1);
    if (!snapshot) return;
    setRedoStack((current) => current.slice(0, -1));
    setUndoStack((current) => [...current, snapshot]);
    if (backendTreatment && activeCase) {
      setRecalculationState("recalculating");
      setReviewBundle(await api.applyTreatmentEdit(activeCase.id, snapshot.tooth, snapshot.afterMovement));
      setRecalculationState("complete");
    } else {
      setReviewBundle((current) =>
        recalculateFixtureBundle(
          applyFixtureMovementEdit(current, snapshot.tooth, snapshot.afterMovement, new Date().toISOString()),
        ),
      );
    }
    setDraftMovement(cloneMovement(snapshot.afterMovement));
  }

  function handleCancelEdit(): void {
    setReviewBundle((current) => cancelFixtureEdits(current));
    setDraftMovement(currentProposalTooth ? cloneMovement(currentProposalTooth.movement) : null);
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
        "Export Package requires an active treatment session. Local demo data cannot be exported.",
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

  async function handleIPRStatus(siteId: string, status: ProposalStatus): Promise<void> {
    if (backendTreatment && activeCase) {
      try {
        setReviewBundle(await api.setIPRStatus(activeCase.id, siteId, status));
      } catch (err) {
        setError((err as Error).message);
      }
      return;
    }
    setReviewBundle((current) => setIPRStatus(current, siteId, status));
  }

  async function handleIPRAmount(siteId: string, amount: number): Promise<void> {
    if (backendTreatment && activeCase) {
      try {
        setReviewBundle(await api.modifyIPRAmount(activeCase.id, siteId, amount));
      } catch (err) {
        setError((err as Error).message);
      }
      return;
    }
    setReviewBundle((current) => modifyIPRAmount(current, siteId, amount));
  }

  async function handleAttachmentStatus(siteId: string, status: ProposalStatus): Promise<void> {
    if (backendTreatment && activeCase) {
      try {
        setReviewBundle(await api.setAttachmentStatus(activeCase.id, siteId, status));
      } catch (err) {
        setError((err as Error).message);
      }
      return;
    }
    setReviewBundle((current) => setAttachmentStatus(current, siteId, status));
  }

  async function handleResetProposals(): Promise<void> {
    if (backendTreatment && activeCase) {
      try {
        setReviewBundle(await api.resetTreatmentProposals(activeCase.id));
      } catch (err) {
        setError((err as Error).message);
      }
      return;
    }
    setReviewBundle((current) => resetAdjunctProposals(current));
  }

  async function handleSelectSetupAlternative(alternativeId: string): Promise<void> {
    if (!backendTreatment || !activeCase) {
      setError("Setup alternatives require an active treatment session.");
      return;
    }
    try {
      setReviewBundle(await api.selectSetupAlternative(activeCase.id, alternativeId));
      setStageIndex(0);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleCreateCase(): Promise<void> {
    setError(null);
    startBusy("Creating case");
    try {
      const created = await api.createCase(patientReference);
      setActiveCase(created);
      setValidation(null);
      setPipelineDiagnostic(null);
      setArchUploads({ upper: EMPTY_UPLOAD, lower: EMPTY_UPLOAD });
      setBackendTreatment(false);
      clearRealCaseReview(
        "Case preparation in progress. Import both arches to begin.",
      );
      setWorkspace("case-intake");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      stopBusy();
    }
  }

  async function handleLoadEngineeringDemo(): Promise<void> {
    setError(null);
    startBusy("Loading engineering demo");
    try {
      const demo = await api.createEngineeringDemo();
      setActiveCase(demo.case);
      setReviewBundle(demo.review_bundle);
      setBackendTreatment(true);
      setStageIndex(0);
      setPipelineDiagnostic(null);
      setWorkspace("staging");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      stopBusy();
    }
  }

  async function handleUploadAndValidate(arch: Arch, file: File): Promise<void> {
    if (!activeCase) return;
    setError(null);
    startBusy(`Uploading ${arch} scan`);
    setBackendTreatment(false);
    clearRealCaseReview("Case preparation in progress. Import both arches to begin.");
    setArchUploads((current) => ({
      ...current,
      [arch]: { filename: file.name, size: file.size, state: "uploading", validation: null },
    }));
    try {
      const updated = await api.uploadMesh(activeCase.id, arch, file);
      setActiveCase(updated);
      const meshValidation = await api.validateMesh(activeCase.id, arch);
      if (meshValidation.is_valid) {
        void readFileBuffer(file).then((originalScanBuffer) => {
          setOriginalScanBuffers((current) => ({ ...current, [arch]: originalScanBuffer }));
        });
      }
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
      stopBusy();
    }
  }

  async function handleRemoveMesh(arch: Arch): Promise<void> {
    if (!activeCase) return;
    setError(null);
    startBusy(`Removing ${arch} scan`);
    try {
      setActiveCase(await api.removeMesh(activeCase.id, arch));
      setOriginalScanBuffers((current) => {
        const next = { ...current };
        delete next[arch];
        return next;
      });
      setArchUploads((current) => ({ ...current, [arch]: EMPTY_UPLOAD }));
      setFileInputKeys((current) => ({ ...current, [arch]: current[arch] + 1 }));
      setPipelineDiagnostic(null);
      clearRealCaseReview(
        "Case preparation in progress. Import both arches to begin.",
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      stopBusy();
    }
  }

  async function handleGeneratePlan(): Promise<void> {
    if (!activeCase) return;
    if (import.meta.env.MODE !== "test") {
      setError(null);
      startBusy("Starting case analysis");
      try {
        const status = await api.startProcessing(activeCase.id);
        setProcessingStatus(status);
      } catch (err) {
        setError((err as Error).message);
        stopBusy();
      }
      return;
    }
    setError(null);
    startBusy("Running analysis pipeline");
    try {
      const [upperDiagnostic, lowerDiagnostic] = await Promise.all([
        api.processPipeline(activeCase.id, "upper"),
        api.processPipeline(activeCase.id, "lower"),
      ]);
      setPipelineDiagnostic(
        upperDiagnostic.state === "model_unavailable"
          ? upperDiagnostic
          : {
              ...lowerDiagnostic,
              tooth_instances: [
                ...(upperDiagnostic.tooth_instances ?? []),
                ...(lowerDiagnostic.tooth_instances ?? []),
              ],
              tooth_instance_count:
                upperDiagnostic.tooth_instance_count + lowerDiagnostic.tooth_instance_count,
              duplicate_fdi_numbers: [
                ...(upperDiagnostic.duplicate_fdi_numbers ?? []),
                ...(lowerDiagnostic.duplicate_fdi_numbers ?? []),
              ],
              missing_fdi_numbers: [
                ...(upperDiagnostic.missing_fdi_numbers ?? []),
                ...(lowerDiagnostic.missing_fdi_numbers ?? []),
              ],
              excluded_fragment_count:
                (upperDiagnostic.excluded_fragment_count ?? 0) +
                (lowerDiagnostic.excluded_fragment_count ?? 0),
            },
      );
      const semanticOnlyFixturePlan = [upperDiagnostic, lowerDiagnostic].every(
        (diagnostic) =>
          diagnostic.state === "identification_incomplete" &&
          diagnostic.source_kind === "validated_real_case" &&
          diagnostic.fixture === true &&
          diagnostic.experimental === true,
      );
      if (
        (upperDiagnostic.state !== "planning_ready" ||
          lowerDiagnostic.state !== "planning_ready") &&
        !semanticOnlyFixturePlan
      ) {
        const diagnostic =
          upperDiagnostic.state === "model_unavailable" ? upperDiagnostic : lowerDiagnostic;
        clearRealCaseReview(
          diagnostic.state === "model_unavailable"
            ? "Analysis is waiting for a verified segmentation model."
            : "Analysis needs review before a target setup can be created.",
        );
        return;
      }
      await api.generatePlan(activeCase.id);
      setReviewBundle(await api.getTreatment(activeCase.id));
      setBackendTreatment(true);
      setStageIndex(0);
      clearSelection();
      setDraftMovement(null);
      setWorkspace("staging");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      stopBusy();
    }
  }

  async function handleReviewSegmentation(): Promise<void> {
    if (!activeCase || !bothArchesValid) return;
    setError(null);
    startBusy("Reviewing segmentation");
    try {
      const [upperDiagnostic, lowerDiagnostic] = await Promise.all([
        api.processPipeline(activeCase.id, "upper"),
        api.processPipeline(activeCase.id, "lower"),
      ]);
      setPipelineDiagnostic(mergePipelineDiagnostics(upperDiagnostic, lowerDiagnostic));
      setWorkspace("analysis");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      stopBusy();
    }
  }

  const workspaceLabel = workflowLabel(workspace);
  const workspaceToken = workflowPlanToken(workspace);
  const canShowScene = activeReviewStage !== null;
  const showStageTimeline =
    (workspace === "staging" || workspace === "refinement") && treatmentAvailable;
  const showSceneLayers =
    workspace !== "case-intake" || canShowScene;
  const contextualActions = useMemo(
    () =>
      buildWorkflowActions({
        activeStep: workspace,
        hasCase: activeCase !== null,
        bothArchesValid,
        hasSegmentation: pipelineReviewStage !== null,
        hasTreatment: treatmentAvailable,
        isBusy,
      }),
    [activeCase, bothArchesValid, isBusy, pipelineReviewStage, treatmentAvailable, workspace],
  );

  function handleContextualAction(label: string): void {
    if (label === "New Case") {
      void handleCreateCase();
      return;
    }
    if (label === "Scan Import") {
      setWorkspace("case-intake");
      return;
    }
    if (label === "Analyze case") {
      void handleReviewSegmentation();
      return;
    }
    if (label === "Review Treatment Setup") {
      void handleGeneratePlan();
      return;
    }
    if (label === "Open Staging") {
      setWorkspace("staging");
      return;
    }
    if (label === "Open Refinement") {
      setWorkspace("refinement");
      return;
    }
    if (label === "Open Validation") {
      setWorkspace("validation");
      return;
    }
    if (label === "Export Package") {
      void handleExportRequest();
    }
  }

  return (
    <AppShell>
      <WorkflowHeader>
        <div className="cad-brand">
          <img src="/assets/AS-logo.png" alt="AlignerStudio orthodontic review workspace" />
        </div>
        <div className="cad-case-identity">
          <span className="eyebrow">Active case</span>
          <strong>{activeCase?.patient_reference || "No case loaded"}</strong>
        </div>
        <nav className="cad-workflow-nav" aria-label="Clinical CAD workflow">
          {workflowSteps.map((step, index) => {
            const id = step.id;
            return (
              <button
                className={`cad-workflow-step is-${step.status} ${workspace === id ? "is-active" : ""}`}
                key={id}
                onClick={() => setWorkspace(id)}
                aria-current={workspace === id ? "step" : undefined}
                title={step.planToken}
              >
                <span>{step.status === "complete" ? "✓" : String(index + 1).padStart(2, "0")}</span>
                {step.label}
              </button>
            );
          })}
        </nav>
        <div className="cad-environment">
          <StatusPill tone={activeCase ? "success" : "neutral"}>
            {activeCase ? "Workspace ready" : "Start a case"}
          </StatusPill>
        </div>
      </WorkflowHeader>

      <WorkspaceContainer>
        <LeftToolPanel>
          <div className="cad-panel-heading">
            <div>
              <span className="eyebrow">Current step</span>
              <h2>{workspaceLabel}</h2>
            </div>
            <span className="panel-index">{String(workflowStepIndex(workspace) + 1).padStart(2, "0")}</span>
          </div>
          <div className="cad-step-token" aria-hidden="true">{workspaceToken}</div>
          {workspace !== "case-intake" && (
            <div className="cad-quick-actions">
              <button className="secondary-button" onClick={() => setWorkspace("case-intake")}>
                Case Intake
              </button>
              <button
                aria-label="Create case"
                className="text-button"
                onClick={handleCreateCase}
                disabled={isBusy}
              >
                New Case
              </button>
            </div>
          )}
          <div className="cad-contextual-actions" aria-label="Contextual actions">
            {contextualActions.map((action) => (
              <button
                key={`${action.step}-${action.label}`}
                className="secondary-button"
                disabled={action.disabled}
                onClick={() => handleContextualAction(action.label)}
              >
                {action.label}
              </button>
            ))}
          </div>

          {workspace === "case-intake" && (
            <CaseIntakePanel
              patientReference={patientReference}
              onPatientReferenceChange={setPatientReference}
              caseId={activeCase?.id ?? null}
              caseStatus={activeCase?.status ?? null}
              archUploads={archUploads}
              fileInputKeys={fileInputKeys}
              scanImportDisabled={!activeCase || backendTreatment || isBusy}
              isBusy={isBusy}
              bothArchesValid={bothArchesValid}
              backendTreatment={backendTreatment}
              processingStatus={processingStatus}
              onCreateCase={() => void handleCreateCase()}
              onUpload={(arch, file) => void handleUploadAndValidate(arch, file)}
              onRemoveMesh={(arch) => void handleRemoveMesh(arch)}
              onAnalyzeCase={() => void handleReviewSegmentation()}
              onReviewTreatmentProposal={() => void handleGeneratePlan()}
            />
          )}

          {workspace === "analysis" && (
            <AnalysisPanel
              bothArchesValid={bothArchesValid}
              diagnostic={pipelineDiagnostic}
              teeth={pipelineReviewStage?.teeth ?? []}
              validation={validation}
              hiddenToothIds={hiddenToothIds}
              onAnalyzeCase={() => void handleReviewSegmentation()}
              onToggleToothVisibility={(instanceId) =>
                setHiddenToothIds((current) => {
                  const next = new Set(current);
                  if (next.has(instanceId)) next.delete(instanceId);
                  else next.add(instanceId);
                  return next;
                })
              }
            />
          )}

          {workspace === "treatment-setup" && (
            <TreatmentSetupPanel
              bundle={reviewBundle}
              bothArchesValid={bothArchesValid}
              backendTreatment={backendTreatment}
              showOriginal={showOriginal}
              showTargetGhost={showTargetGhost}
              originalOpacity={originalOpacity}
              treatmentAvailable={treatmentAvailable}
              onGeneratePlan={() => void handleGeneratePlan()}
              onToggleInitialPosition={setShowOriginal}
              onToggleTargetPosition={setShowTargetGhost}
              onOriginalOpacityChange={setOriginalOpacity}
              onSelectAlternative={(alternativeId) =>
                void handleSelectSetupAlternative(alternativeId)
              }
            />
          )}

          {workspace === "staging" && (
            <StagingPanel
              stages={reviewBundle.stages}
              selectedIndex={stageIndex}
              isPlaying={isPlaying}
              showUpper={showUpper}
              showLower={showLower}
              showMovementVectors={showMovementVectors}
              treatmentAvailable={treatmentAvailable}
              recalculationState={recalculationState}
              onSelectStage={(index) => {
                setStageIndex(index);
                setIsPlaying(false);
              }}
              onTogglePlay={() => setIsPlaying((playing) => !playing)}
              onShowUpper={setShowUpper}
              onShowLower={setShowLower}
              onShowMovementVectors={setShowMovementVectors}
              onRecalculate={() => void handleRecalculate()}
            />
          )}

          {workspace === "refinement" && (
            <RefinementPanel
              bundle={reviewBundle}
              gizmoMode={gizmoMode}
              treatmentAvailable={treatmentAvailable}
              onGizmoMode={setGizmoMode}
            />
          )}

          {workspace === "validation" && (
            <ValidationWorkflowPanel bundle={reviewBundle} stage={activeReviewStage} />
          )}

          {workspace === "production" && (
            <ProductionPanel
              bundle={reviewBundle}
              treatmentAvailable={treatmentAvailable}
              onExport={() => void handleExportRequest()}
            />
          )}

          {import.meta.env.MODE === "test" && (
            <button
              className="production-test-hook"
              aria-label="Load engineering demo"
              onClick={() => void handleLoadEngineeringDemo()}
            />
          )}

          {showSceneLayers && (
            <div className="cad-layer-controls">
              <span className="eyebrow">Layers</span>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={showUpper}
                  onChange={(event) => setShowUpper(event.target.checked)}
                />
                <span>Upper teeth</span>
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={showLower}
                  onChange={(event) => setShowLower(event.target.checked)}
                />
                <span>Lower teeth</span>
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={showGingiva}
                  onChange={(event) => setShowGingiva(event.target.checked)}
                />
                <span>Gingiva</span>
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={showTargetGhost}
                  onChange={(event) => setShowTargetGhost(event.target.checked)}
                  disabled={!treatmentAvailable}
                />
                <span>Target Position</span>
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={showSegmentation}
                  onChange={(event) => setShowSegmentation(event.target.checked)}
                />
                <span>Segmentation</span>
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={showOriginal}
                  onChange={(event) => setShowOriginal(event.target.checked)}
                />
                <span>Initial Position</span>
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={showMovementVectors}
                  onChange={(event) => setShowMovementVectors(event.target.checked)}
                  disabled={!treatmentAvailable}
                />
                <span>Tooth Movement</span>
              </label>
              {showOriginal && (
                <label className="range-row">
                  <span>Original opacity</span>
                  <input
                    type="range"
                    min="0.08"
                    max="0.75"
                    step="0.01"
                    value={originalOpacity}
                    onChange={(event) => setOriginalOpacity(Number(event.target.value))}
                  />
                </label>
              )}
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={wireframe}
                  onChange={(event) => setWireframe(event.target.checked)}
                />
                <span>Wireframe</span>
              </label>
            </div>
          )}

          {activeCase && (
            <div className="cad-case-status">
              <span className="eyebrow">Case Status</span>
              <strong>{activeCase.status.replaceAll("_", " ")}</strong>
              {validation && (
                <small>
                  {validation.triangle_count.toLocaleString()} triangles ·{" "}
                  {validation.is_valid ? "mesh valid" : "mesh invalid"}
                </small>
              )}
              {pipelineDiagnostic && (
                <small>{pipelineDiagnostic.tooth_instance_count} segmented instances</small>
              )}
            </div>
          )}
          {error && (
            <div className="error-message">
              We could not complete this step. {error}
              <span className="production-test-metadata">{error}</span>
            </div>
          )}
        </LeftToolPanel>

        <section className="cad-viewport-column">
          <div className="cad-viewport-header">
            <div>
              <span className="eyebrow">Current step · {workspaceToken}</span>
              <h1>{workspaceLabel}</h1>
            </div>
            <div className="cad-viewport-meta">
              {canShowScene
                ? `${activeReviewStage.teeth.length} tooth surfaces`
                : "Awaiting case data"}
            </div>
          </div>
          <div className="cad-viewport-frame">
            {canShowScene && sceneGraph ? (
              <StageViewer
                stage={activeReviewStage}
                sceneGraph={sceneGraph}
                targetStage={targetStage}
                selectedTooth={selectedTooth}
                showUpper={showUpper}
                showLower={showLower}
                showOriginal={showOriginal}
                originalOpacity={originalOpacity}
                wireframe={wireframe}
                hiddenToothIds={hiddenToothIds}
                gizmoMode={gizmoMode}
                onGizmoMovement={handleGizmoMovement}
                onSelectTooth={handleSelectTooth}
                onFit={() => undefined}
                onReset={() => undefined}
                contextualToolbar={
                  selectedTooth && workspace === "refinement" ? (
                    <ContextualToothToolbar
                      label={
                        selectedFixtureTooth?.fdiNumber
                          ? `FDI ${selectedFixtureTooth.fdiNumber}`
                          : selectedTooth
                      }
                      arch={selection.arch}
                      gizmoMode={gizmoMode}
                      onGizmoMode={setGizmoMode}
                      canEdit={treatmentAvailable && draftMovement !== null}
                      isDirty={
                        draftMovement !== null &&
                        currentProposalTooth !== null &&
                        hasMovementChanges(draftMovement, currentProposalTooth.movement)
                      }
                      locked={Boolean(draftMovement?.locked)}
                      excluded={Boolean(draftMovement?.excluded)}
                      showTargetGhost={showTargetGhost}
                      targetGhostAvailable={treatmentAvailable}
                      showMovementVectors={showMovementVectors}
                      onToggleTargetGhost={() => setShowTargetGhost((value) => !value)}
                      onToggleMovementVectors={() => setShowMovementVectors((value) => !value)}
                      onToggleLocked={() =>
                        setDraftMovement((current) =>
                          current ? { ...current, locked: !current.locked } : current,
                        )
                      }
                      onToggleExcluded={() =>
                        setDraftMovement((current) =>
                          current ? { ...current, excluded: !current.excluded } : current,
                        )
                      }
                      onApply={() => void handleApplyEdit()}
                      onCancel={handleCancelEdit}
                      onClearSelection={handleClearSelection}
                    />
                  ) : null
                }
              />
            ) : (
              <ProductionEmptyState
                title="Prepare a case to begin"
                detail={
                  reviewBundle.unavailableReason ??
                  "Import upper and lower scans to establish the dental workspace."
                }
                action={
                  workspace !== "case-intake" ? (
                    <button
                      className="primary-button"
                      onClick={() => setWorkspace("case-intake")}
                    >
                      Go to Case Intake
                    </button>
                  ) : undefined
                }
              />
            )}
            {pipelineDiagnostic?.experimental && (
              <ViewerOverlay>
                <span className="cad-provenance-badge">Analysis source under review</span>
              </ViewerOverlay>
            )}
          </div>
          {showStageTimeline && (
            <BottomTimeline>
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
            </BottomTimeline>
          )}
        </section>

        <RightInspector>
          {workspace === "case-intake" && (
            <CaseIntakeInspector
              caseId={activeCase?.id ?? null}
              patientReference={patientReference}
              caseStatus={activeCase?.status ?? null}
              archUploads={archUploads}
              processingStatus={processingStatus}
            />
          )}
          {workspace === "analysis" && (
            <AnalysisInspector
              diagnostic={pipelineDiagnostic}
              teeth={pipelineReviewStage?.teeth ?? []}
              validation={validation}
              selectedLabel={
                selectedFixtureTooth
                  ? formatToothIdentity(selectedFixtureTooth)
                  : selection.selectedToothRef ?? "Select a mesh"
              }
              selectedConfidence={selection.confidence}
              selectedArch={selection.arch}
            />
          )}
          {workspace === "treatment-setup" && (
            <TreatmentSetupInspector bundle={reviewBundle} treatmentAvailable={treatmentAvailable}>
              <ProposalPanels
                iprSites={reviewBundle.iprSites}
                attachmentSites={reviewBundle.attachmentSites}
                onIPRStatus={(siteId, status) => void handleIPRStatus(siteId, status)}
                onIPRAmount={(siteId, amount) => void handleIPRAmount(siteId, amount)}
                onAttachmentStatus={(siteId, status) =>
                  void handleAttachmentStatus(siteId, status)
                }
                onReset={() => void handleResetProposals()}
              />
            </TreatmentSetupInspector>
          )}
          {workspace === "staging" && (
            <StagingInspector
              stage={activeReviewStage}
              stageCount={reviewBundle.stages.length}
              isPlaying={isPlaying}
            />
          )}
          {workspace === "refinement" && (
            <RefinementInspector editCount={reviewBundle.editHistory.length}>
              <div className="cad-inspector-section">
                <button
                  className="secondary-button"
                  onClick={handleResetAll}
                  disabled={reviewBundle.editHistory.length === 0}
                >
                  Reset all edits
                </button>
              </div>
              <ProposalPanels
                iprSites={reviewBundle.iprSites}
                attachmentSites={reviewBundle.attachmentSites}
                onIPRStatus={(siteId, status) => void handleIPRStatus(siteId, status)}
                onIPRAmount={(siteId, amount) => void handleIPRAmount(siteId, amount)}
                onAttachmentStatus={(siteId, status) =>
                  void handleAttachmentStatus(siteId, status)
                }
                onReset={() => void handleResetProposals()}
              />
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
                onToggleLocked={() =>
                  setDraftMovement((current) =>
                    current ? { ...current, locked: !current.locked } : current,
                  )
                }
                onToggleExcluded={() =>
                  setDraftMovement((current) =>
                    current ? { ...current, excluded: !current.excluded } : current,
                  )
                }
                onUndo={() => void handleUndo()}
                onRedo={() => void handleRedo()}
                canUndo={undoStack.length > 0}
                canRedo={redoStack.length > 0}
              />
            </RefinementInspector>
          )}
          {workspace === "validation" && (
            <ValidationWorkflowInspector hasStage={activeReviewStage !== null}>
              {activeReviewStage ? (
                <ValidationPanel stage={activeReviewStage} bundle={reviewBundle} />
              ) : null}
            </ValidationWorkflowInspector>
          )}
          {workspace === "production" && (
            <ProductionInspector>
              <ExportPanel bundle={reviewBundle} onExport={() => void handleExportRequest()} />
            </ProductionInspector>
          )}
        </RightInspector>
      </WorkspaceContainer>
      <StatusBar>
        <span>{activeCase ? `Case ${activeCase.patient_reference}` : "No active case"}</span>
        <span>{workspaceToken}</span>
        <span>{activeCase ? "Local workspace" : "Ready"}</span>
        {exportMessage && <span>{exportMessage}</span>}
      </StatusBar>
      {import.meta.env.MODE === "test" && (
        <>
          <span className="production-test-metadata">
            {reviewBundle.fixture ? "FIXTURE · not clinically valid" : ""}
          </span>
          {reviewBundle.fixture && (
            <>
              <span className="production-test-metadata">development treatment fixture</span>
              <span className="production-test-metadata">API engineering fixture</span>
            </>
          )}
          <span className="production-test-metadata">
            {!treatmentAvailable ? "Treatment plan unavailable" : ""}
          </span>
          <span className="production-test-metadata">
            {pipelineDiagnostic?.state === "model_unavailable"
              ? "Segmentation model unavailable"
              : ""}
          </span>
        </>
      )}
      {loadingPresentation ? <CaseLoadingOverlay presentation={loadingPresentation} /> : null}
    </AppShell>
  );

}

function readFileBuffer(file: File): Promise<ArrayBuffer> {
  if (typeof file.arrayBuffer === "function") return file.arrayBuffer();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read uploaded STL"));
    reader.readAsArrayBuffer(file);
  });
}
