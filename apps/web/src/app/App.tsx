import { useEffect, useMemo, useRef, useState } from "react";
import type {
  Case,
  CaseDentalIntelligencePayload,
  IntakeArtifact,
  MeshValidationResult,
  PreparationJob,
  SegmentationJob,
} from "@alignerstudio/contracts";
import { createSceneLayerRegistry } from "@alignerstudio/types";
import { api, type PipelineDiagnostic, type ProcessingStatus } from "../api/client";
import { buildCaseIntakeReadiness } from "../caseIntake";
import { ConfirmDialog } from "../design-system";
import { AnalysisPanel } from "../components/AnalysisPanel";
import { CaseIntakePanel } from "../components/CaseIntakePanel";
import type { PreparationPreview, PreparationRequest } from "../components/ScanPreparationForm";
import type { SegmentationReviewRequest } from "../components/SegmentationReviewForm";
import { ProductionPanel } from "../components/ProductionPanel";
import { RefinementPanel } from "../components/RefinementPanel";
import { StagingPanel } from "../components/StagingPanel";
import { TreatmentSetupPanel } from "../components/TreatmentSetupPanel";
import { ValidationWorkflowPanel } from "../components/ValidationWorkflowPanel";
import { ContextualToothToolbar } from "../components/ContextualToothToolbar";
import { InspectionPanel } from "../components/InspectionPanel";
import { type ArchIsolationMode } from "../components/WorkspaceViewportChrome";
import { ProposalPanels } from "../components/ProposalPanels";
import { StageTimeline } from "../components/StageTimeline";
import { ValidationPanel } from "../components/ValidationPanel";
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
  TreatmentSetupComparison,
} from "../review/types";
import { StageViewer } from "../viewer/StageViewer";
import { createDentalSceneGraph } from "../viewer/sceneGraph";
import { findToothByKey } from "../viewer/toothKey";
import { useToothSelection } from "../viewer/useToothSelection";
import {
  AdaptiveInspector,
  ContextualWorkspaceToolbar,
  DentalArchMap,
  PrimaryStatus,
  SegmentationReviewStrip,
  SmartWidgets,
  WorkflowOrientation,
} from "../components/workspace/ClinicalChrome";
import {
  buildDentalMapEntries,
  buildFeedbackModel,
  buildInspectorModel,
  buildSegmentationReviewModel,
  deleteShortcutEffect,
  isTextEntryTarget,
  matchWorkspaceShortcut,
  toothReviewLabel,
  type CameraCommand,
  type ToothLabelMode,
} from "../interaction/model";
import type { NextAction } from "../interaction/nextAction";
import { dedupeNotice, workflowOrientation } from "../interaction/smartUx";
import { commandIdForShortcut, resolveToolbar, viewportCommandMutatesClinicalState } from "../interaction/toolbar";
import { resolveWidgets } from "../interaction/widgets";
import { claimTerminalLoad } from "../performance/processingLifecycle";
import { nextLabelMode } from "../viewer/presentation/labelPolicy";
import {
  beginTransformTransaction,
  buildToothInteractionState,
  canTransformTooth,
  normalizeClientEditReason,
  updateTransformTransaction,
  type EditProvenanceReason,
  type InteractionTransaction,
} from "../viewer/toothInteraction";
import {
  AppShell,
  BottomTimeline,
  LeftToolPanel,
  RightInspector,
  ViewerOverlay,
  WorkflowHeader,
  WorkspaceContainer,
} from "../components/workspace/WorkspacePrimitives";
import {
  resolveWorkflow,
  resolveWorkflowNavigation,
  workflowLabel,
  workflowStepFromHistory,
  workflowStepIndex,
  type WorkflowStepId,
} from "../workflow";
import { CaseLoadingOverlay, ProductionEmptyState } from "../components/production/ProductionPrimitives";
import { resolveLoadingPresentation } from "../components/production/loadingPresentation";
import {
  readRememberedActiveCaseId,
  readRememberedActiveWorkspace,
  rememberActiveCaseId,
  rememberActiveWorkspace,
  resolveRestoredWorkspace,
} from "../caseWorkspacePersistence";

type WorkspaceId = WorkflowStepId;

type Arch = "upper" | "lower";
type UploadState = "empty" | "uploading" | "valid" | "invalid" | "error";

interface ArchUpload {
  filename: string;
  size: number;
  state: UploadState;
  validation: MeshValidationResult | null;
  intake?: IntakeArtifact | null;
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
      validationStatus:
        tooth.fixture || tooth.provenance === "fixture" || tooth.experimental ? "unavailable" : "pass",
      validationMessage:
        tooth.fixture || tooth.provenance === "fixture" || tooth.experimental
          ? "Fixture/test-only surface. Treatment validation was not run."
          : "Treatment validation was not run on this surface.",
      provenance: tooth.provenance,
      fixture: tooth.fixture,
      experimental: tooth.experimental,
    }));
  if (!diagnostic || teeth.length === 0) return null;
  return {
    index: 0,
    stageId: "toothinstancenet-validation-stage",
    teeth,
    validationStatus:
      diagnostic.fixture || diagnostic.provenance === "fixture"
        ? "unavailable"
        : diagnostic.duplicate_fdi_numbers?.length || diagnostic.missing_fdi_numbers?.length
          ? "warning"
          : "pass",
    collisionCount: 0,
    proximityCount: 0,
    contactCount: 0,
    warnings: [
      ...(diagnostic.duplicate_fdi_numbers?.length ? [`Duplicate FDI: ${diagnostic.duplicate_fdi_numbers.join(", ")}`] : []),
      ...(diagnostic.missing_fdi_numbers?.length
        ? [`Identity/data not established (reported FDI gap: ${diagnostic.missing_fdi_numbers.join(", ")})`]
        : []),
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
  const [preparationPreview, setPreparationPreview] = useState<{
    arch: Arch;
    body: PreparationPreview;
  } | null>(null);
  const [preparationJob, setPreparationJob] = useState<{ arch: Arch; job: PreparationJob } | null>(
    null,
  );
  const [segmentationJob, setSegmentationJob] = useState<{ arch: Arch; job: SegmentationJob } | null>(
    null,
  );
  const [pipelineDiagnostic, setPipelineDiagnostic] = useState<PipelineDiagnostic | null>(null);
  const [dentalIntelligence, setDentalIntelligence] =
    useState<CaseDentalIntelligencePayload | null>(null);
  const [backendTreatment, setBackendTreatment] = useState(false);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [busyActivity, setBusyActivity] = useState<string | null>(null);
  const [stageIndex, setStageIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showUpper, setShowUpper] = useState(true);
  const [showLower, setShowLower] = useState(true);
  const [archMode, setArchMode] = useState<ArchIsolationMode>("both");
  const [isolateSelectedTooth, setIsolateSelectedTooth] = useState(false);
  const [labelMode, setLabelMode] = useState<ToothLabelMode>("selected");
  const [hoveredToothKey, setHoveredToothKey] = useState<string | null>(null);
  const [cameraCommand, setCameraCommand] = useState<{ nonce: number; command: CameraCommand } | null>(null);
  const [inspectorMinimized, setInspectorMinimized] = useState(false);
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
  const [confirmNewCaseOpen, setConfirmNewCaseOpen] = useState(false);
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
  const [dependencyNotice, setDependencyNotice] = useState<string | null>(null);
  const ignoreWorkspaceHistory = useRef(false);
  const historyBoot = useRef(true);
  const workspaceHydrated = useRef(false);
  const [gizmoMode, setGizmoMode] = useState<"translate" | "rotate">("translate");
  const [undoStack, setUndoStack] = useState<EditSnapshot[]>([]);
  const [redoStack, setRedoStack] = useState<EditSnapshot[]>([]);
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus | null>(null);
  const [editReason, setEditReason] = useState<EditProvenanceReason>("doctor_edit");
  const [transformTransaction, setTransformTransaction] = useState<InteractionTransaction | null>(
    null,
  );
  const [versionCompare, setVersionCompare] = useState<TreatmentSetupComparison | null>(null);

  const fixtureStage = reviewBundle.stages[stageIndex] ?? null;
  const treatmentAvailable = reviewBundle.realDataAvailable && fixtureStage !== null;
  const pipelineReviewStage = useMemo(() => pipelineStage(pipelineDiagnostic), [pipelineDiagnostic]);
  const activeReviewStage = treatmentAvailable ? fixtureStage : pipelineReviewStage;
  const { selection, selectTooth, clearSelection, multiSelectedKeys, preserveAcrossTeeth } =
    useToothSelection(activeReviewStage?.teeth ?? []);
  const selectedTooth = selection.selectedToothRef;

  useEffect(() => {
    preserveAcrossTeeth(activeReviewStage?.teeth ?? []);
  }, [activeReviewStage, preserveAcrossTeeth]);

  useEffect(() => {
    if (archMode === "both") {
      setShowUpper(true);
      setShowLower(true);
    } else if (archMode === "upper") {
      setShowUpper(true);
      setShowLower(false);
    } else {
      setShowUpper(false);
      setShowLower(true);
    }
  }, [archMode]);

  const isolatedArch = archMode === "both" ? null : archMode;
  const isolatedToothKey = isolateSelectedTooth ? selectedTooth : null;
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
  // Inspector context is not a dependency. Changing it does not rebuild geometry or the BVH.
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
      : findToothByKey(reviewBundle.stages[0]?.teeth, selectedTooth);
  const currentProposalTooth =
    selectedTooth === null
      ? null
      : findToothByKey(reviewBundle.stages.at(-1)?.teeth, selectedTooth);
  const toothInteractionState = useMemo(() => {
    if (!selectedFixtureTooth || !draftMovement || !currentProposalTooth) return null;
    return buildToothInteractionState({
      caseId: activeCase?.id ?? null,
      tooth: selectedFixtureTooth,
      draft: draftMovement,
      base: currentProposalTooth.movement,
      selected: true,
      transforming: transformTransaction != null,
    });
  }, [
    activeCase?.id,
    currentProposalTooth,
    draftMovement,
    selectedFixtureTooth,
    transformTransaction,
  ]);
  const bothArchesValid =
    archUploads.upper.state === "valid" && archUploads.lower.state === "valid";
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
    // WP-04: dispose interaction/undo state on case change — prevent stale transforms.
    setUndoStack([]);
    setRedoStack([]);
    setTransformTransaction(null);
    setEditReason("doctor_edit");
    setIsolateSelectedTooth(false);
    setArchMode("both");
    setVersionCompare(null);
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
    // Persist only when a case is active. Clearing on null would wipe the
    // remembered id before the mount-time rehydrate effect can read it.
    if (activeCase?.id) {
      rememberActiveCaseId(activeCase.id);
    }
  }, [activeCase?.id]);

  useEffect(() => {
    if (!readRememberedActiveCaseId()) workspaceHydrated.current = true;
  }, []);

  useEffect(() => {
    if (!workspaceHydrated.current) return;
    if (activeCase?.id) {
      rememberActiveWorkspace(workspace);
    }
  }, [activeCase?.id, workspace]);

  useEffect(() => {
    const onPop = (event: PopStateEvent) => {
      const step = workflowStepFromHistory(event.state);
      if (!step) return;
      ignoreWorkspaceHistory.current = true;
      setDependencyNotice(null);
      setWorkspace(step);
    };
    window.addEventListener("popstate", onPop);
    if (!workflowStepFromHistory(window.history.state)) {
      window.history.replaceState({ workflowStep: workspace }, "");
    }
    return () => window.removeEventListener("popstate", onPop);
  }, [workspace]);

  useEffect(() => {
    if (ignoreWorkspaceHistory.current) {
      ignoreWorkspaceHistory.current = false;
      historyBoot.current = false;
      return;
    }
    const current = workflowStepFromHistory(window.history.state);
    if (current === workspace) {
      historyBoot.current = false;
      return;
    }
    // The first paint is case intake. Do not cover a reloaded step with that default.
    if (historyBoot.current && current && workspace === "case-intake") {
      historyBoot.current = false;
      return;
    }
    historyBoot.current = false;
    window.history.pushState({ workflowStep: workspace }, "");
  }, [workspace]);

  useEffect(() => {
    let cancelled = false;
    const rememberedId = readRememberedActiveCaseId();
    if (!rememberedId) return;
    const rememberedWorkspace =
      readRememberedActiveWorkspace() ?? workflowStepFromHistory(window.history.state);
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
        let processingCompleted = false;
        try {
          const status = await api.getProcessingStatus(rememberedId);
          if (!cancelled && status) {
            setProcessingStatus(status);
            processingCompleted = status.stage_status === "COMPLETED";
          }
        } catch {
          // No processing status yet.
        }
        try {
          const bundle = await api.getTreatment(rememberedId);
          if (cancelled) return;
          setReviewBundle(bundle);
          setBackendTreatment(true);
          workspaceHydrated.current = true;
          setWorkspace(
            resolveRestoredWorkspace({
              remembered: rememberedWorkspace,
              hasTreatment: true,
              hasProcessingCompleted: processingCompleted,
            }),
          );
        } catch {
          // Treatment not composed yet — case metadata alone is enough to continue intake.
          if (!cancelled) {
            workspaceHydrated.current = true;
            setWorkspace(
              resolveRestoredWorkspace({
                remembered: rememberedWorkspace,
                hasTreatment: false,
                hasProcessingCompleted: processingCompleted,
              }),
            );
          }
        }
      } catch {
        workspaceHydrated.current = true;
        rememberActiveCaseId(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const processingMounted = useRef(true);
  const completionLoadJob = useRef<string | null>(null);
  useEffect(() => {
    processingMounted.current = true;
    return () => {
      processingMounted.current = false;
    };
  }, []);

  useEffect(() => {
    const isProcessing = processingStatus?.stage_status === "PROCESSING";
    if (!activeCase || !isProcessing) return;
    const caseId = activeCase.id;
    const activeJobId = processingStatus?.job_id ?? null;
    if (completionLoadJob.current && activeJobId && completionLoadJob.current !== activeJobId) {
      completionLoadJob.current = null;
    }
    let cancelled = false;
    const timer = window.setInterval(() => {
      void api.getProcessingStatus(caseId).then((status) => {
        if (cancelled) return;
        setProcessingStatus(status);
        if (status.stage_status === "COMPLETED") {
          if (!claimTerminalLoad(completionLoadJob, status.job_id)) return;
          setBusyActivity("Loading treatment proposal");
          void Promise.all([
            api.getTreatment(caseId),
            api.getDentalIntelligence(caseId).catch(() => null),
          ]).then(([bundle, intelligence]) => {
            if (!processingMounted.current) return;
            setReviewBundle(bundle);
            if (intelligence) setDentalIntelligence(intelligence);
            setBackendTreatment(true);
            setStageIndex(0);
            setWorkspace("staging");
            stopBusy();
          }).catch((error: Error) => {
            if (!processingMounted.current) return;
            setError(error.message);
            stopBusy();
          });
        } else if (
          status.stage_status === "FAILED" ||
          status.stage_status === "CANCELLED" ||
          status.stage_status === "STALE" ||
          status.stage_status === "INTERRUPTED"
        ) {
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
  }, [activeCase, processingStatus?.stage_status, processingStatus?.job_id]);

  function handleSelectTooth(toothNumber: string, options?: { additive?: boolean }): void {
    selectTooth(toothNumber, options);
    const tooth =
      findToothByKey(reviewBundle.stages.at(-1)?.teeth, toothNumber) ??
      findToothByKey(activeReviewStage?.teeth, toothNumber);
    setDraftMovement(tooth ? cloneMovement(tooth.movement) : null);
    setTransformTransaction(null);
    setEditReason("doctor_edit");
  }

  function handleClearSelection(): void {
    clearSelection();
    setDraftMovement(null);
    setTransformTransaction(null);
    setEditReason("doctor_edit");
  }

  function handleGizmoMovement(movement: MovementSummary): void {
    if (!draftMovement || !canTransformTooth(draftMovement)) return;
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
    setEditReason("gizmo_edit");
    setTransformTransaction((current) => {
      if (!selectedTooth) return current;
      if (!current || current.toothKey !== selectedTooth) {
        return updateTransformTransaction(
          beginTransformTransaction(selectedTooth, draftMovement, "gizmo_edit"),
          next,
        );
      }
      return updateTransformTransaction(current, next);
    });
    setDraftMovement(next);
  }

  function handleDraftChange(movement: MovementSummary): void {
    if (!draftMovement) {
      setDraftMovement(movement);
      setEditReason("numeric_edit");
      return;
    }
    const lockedOrExcluded = Boolean(draftMovement.locked || draftMovement.excluded);
    if (lockedOrExcluded && !canTransformTooth(movement)) {
      // Only lock/exclude flag changes are allowed while blocked.
      const flagsOnly =
        !hasMovementChanges(
          { ...draftMovement, locked: false, excluded: false },
          { ...movement, locked: false, excluded: false },
        );
      if (!flagsOnly) return;
    }
    setEditReason("numeric_edit");
    setDraftMovement(movement);
  }

  async function handleApplyEdit(): Promise<void> {
    if (selectedTooth === null || !draftMovement) return;
    const beforeMovement = currentProposalTooth?.movement ?? draftMovement;
    if (
      !canTransformTooth(beforeMovement) &&
      hasMovementChanges(
        { ...beforeMovement, locked: false, excluded: false },
        { ...draftMovement, locked: false, excluded: false },
      )
    ) {
      setError(
        beforeMovement.locked
          ? `Tooth ${selectedTooth} is locked; unlock before changing movement`
          : `Tooth ${selectedTooth} is excluded; include before changing movement`,
      );
      return;
    }
    const reason = normalizeClientEditReason(editReason);
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
        setReviewBundle(
          await api.applyTreatmentEdit(activeCase.id, selectedTooth, draftMovement, reason),
        );
        setUndoStack((current) => [...current, snapshot]);
        setRedoStack([]);
        setTransformTransaction(null);
        setEditReason("doctor_edit");
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
        applyFixtureMovementEdit(
          current,
          selectedTooth,
          draftMovement,
          new Date().toISOString(),
          reason,
        ),
      ),
    );
    setUndoStack((current) => [...current, snapshot]);
    setRedoStack([]);
    setTransformTransaction(null);
    setEditReason("doctor_edit");
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
      setReviewBundle(
        await api.applyTreatmentEdit(
          activeCase.id,
          snapshot.tooth,
          snapshot.beforeMovement,
          "system_restore",
        ),
      );
      setRecalculationState("complete");
    } else {
      setReviewBundle(snapshot.before);
    }
    setDraftMovement(cloneMovement(snapshot.beforeMovement));
    setEditReason("system_restore");
  }

  async function handleRedo(): Promise<void> {
    const snapshot = redoStack.at(-1);
    if (!snapshot) return;
    setRedoStack((current) => current.slice(0, -1));
    setUndoStack((current) => [...current, snapshot]);
    if (backendTreatment && activeCase) {
      setRecalculationState("recalculating");
      setReviewBundle(
        await api.applyTreatmentEdit(
          activeCase.id,
          snapshot.tooth,
          snapshot.afterMovement,
          "system_restore",
        ),
      );
      setRecalculationState("complete");
    } else {
      setReviewBundle((current) =>
        recalculateFixtureBundle(
          applyFixtureMovementEdit(
            current,
            snapshot.tooth,
            snapshot.afterMovement,
            new Date().toISOString(),
            "system_restore",
          ),
        ),
      );
    }
    setDraftMovement(cloneMovement(snapshot.afterMovement));
    setEditReason("system_restore");
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

  async function handleRegenerateStaging(): Promise<void> {
    if (!backendTreatment || !activeCase) {
      setError("Staging regenerate requires an active treatment session.");
      return;
    }
    setRecalculationState("recalculating");
    try {
      setReviewBundle(
        await api.regenerateStaging(activeCase.id, "Doctor-requested staging regenerate", "doctor"),
      );
      setStageIndex(0);
      setRecalculationState("complete");
    } catch (err) {
      setError((err as Error).message);
      setRecalculationState("idle");
    }
  }

  async function handleSaveStagingVersion(): Promise<void> {
    if (!backendTreatment || !activeCase) {
      setError("Saving a staging version requires an active treatment session.");
      return;
    }
    startBusy("Saving staging version");
    try {
      setReviewBundle(
        await api.saveStagingVersion(activeCase.id, "Doctor-saved staging version", "doctor"),
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      stopBusy();
    }
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

  async function handleSaveSetupVersion(description: string): Promise<void> {
    if (!backendTreatment || !activeCase) {
      setError("Saving a setup version requires an active treatment session.");
      return;
    }
    startBusy("Saving treatment setup version");
    try {
      setReviewBundle(await api.saveTreatmentVersion(activeCase.id, description, "doctor"));
      setVersionCompare(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      stopBusy();
    }
  }

  async function handleRestoreSetupVersion(versionId: string): Promise<void> {
    if (!backendTreatment || !activeCase) {
      setError("Restoring a setup version requires an active treatment session.");
      return;
    }
    startBusy("Restoring treatment setup version");
    try {
      setReviewBundle(await api.restoreTreatmentVersion(activeCase.id, versionId));
      setStageIndex(0);
      setDraftMovement(null);
      setVersionCompare(null);
      setUndoStack([]);
      setRedoStack([]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      stopBusy();
    }
  }

  async function handleCompareSetupVersions(
    leftVersionId: string,
    rightVersionId: string,
  ): Promise<void> {
    if (!backendTreatment || !activeCase) {
      setError("Comparing setup versions requires an active treatment session.");
      return;
    }
    try {
      setVersionCompare(
        await api.compareTreatmentVersions(activeCase.id, leftVersionId, rightVersionId),
      );
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
      setDentalIntelligence(null);
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
      setDentalIntelligence(null);
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
      const intake = updated.intake_artifacts?.find((item) => item.arch?.arch === arch) ?? null;
      setArchUploads((current) => ({
        ...current,
        [arch]: {
          filename: file.name,
          size: file.size,
          state: meshValidation.is_valid ? "valid" : "invalid",
          validation: meshValidation,
          intake,
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

  function rememberIntake(arch: Arch, updated: Case): void {
    const intake = updated.intake_artifacts?.find((item) => item.arch?.arch === arch) ?? null;
    setArchUploads((current) => ({
      ...current,
      [arch]: { ...current[arch], intake },
    }));
  }

  async function handlePrepare(arch: Arch, request: PreparationRequest): Promise<void> {
    if (!activeCase) return;
    setError(null);
    const background =
      (request.action === "preview" || request.action === "apply") &&
      (request.operation === "orient" || request.operation === "trim" || request.operation === "cleanup");
    if (background) {
      try {
        const mode = request.action === "preview" ? "preview" : "apply";
        const queued = await api.submitPreparationJob(
          activeCase.id,
          arch,
          request.operation ?? "",
          request.parameters ?? {},
          mode,
        );
        setPreparationJob({ arch, job: queued });
        const finished = await api.waitForPreparationJob(activeCase.id, arch, queued.job_id, (job) => {
          setPreparationJob({ arch, job });
        });
        setPreparationJob({ arch, job: finished });
        if (finished.state === "failed") {
          setError(finished.error?.message ?? "Preparation failed.");
          return;
        }
        if (finished.state === "cancelled") return;
        if (mode === "preview") {
          setPreparationPreview({
            arch,
            body: (finished.result ?? {}) as PreparationPreview,
          });
          return;
        }
        const updated = await api.getCase(activeCase.id);
        setActiveCase(updated);
        setPreparationPreview(null);
        rememberIntake(arch, updated);
      } catch (err) {
        setError((err as Error).message);
      }
      return;
    }
    startBusy(`Preparing ${arch} scan`);
    try {
      const updated =
        request.action === "undo"
          ? await api.undoPreparation(activeCase.id, arch)
          : request.action === "reset"
            ? await api.resetPreparation(activeCase.id, arch)
            : request.action === "accept"
              ? await api.acceptPreparation(activeCase.id, arch)
              : await api.applyPreparation(
                  activeCase.id,
                  arch,
                  request.operation ?? "",
                  request.parameters ?? {},
                );
      setActiveCase(updated);
      setPreparationPreview(null);
      rememberIntake(arch, updated);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      stopBusy();
    }
  }

  async function handleStartSegmentation(arch: Arch): Promise<void> {
    if (!activeCase) return;
    setError(null);
    try {
      const queued = await api.submitSegmentationJob(activeCase.id, arch);
      setSegmentationJob({ arch, job: queued });
      const finished = await api.waitForSegmentationJob(activeCase.id, arch, queued.job_id, (job) => {
        setSegmentationJob({ arch, job });
      });
      setSegmentationJob({ arch, job: finished });
      const updated = await api.getCase(activeCase.id);
      setActiveCase(updated);
      rememberIntake(arch, updated);
      if (finished.state === "failed" && !finished.blocked) {
        setError(finished.error?.message ?? "Segmentation failed.");
      }
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleSegmentationReview(arch: Arch, request: SegmentationReviewRequest): Promise<void> {
    if (!activeCase) return;
    setError(null);
    try {
      const updated = await api.reviewSegmentation(activeCase.id, arch, request.action, request);
      setActiveCase(updated);
      rememberIntake(arch, updated);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleCancelPreparationJob(): Promise<void> {
    if (!activeCase || !preparationJob) return;
    try {
      const cancelled = await api.cancelPreparationJob(
        activeCase.id,
        preparationJob.arch,
        preparationJob.job.job_id,
      );
      setPreparationJob({ arch: preparationJob.arch, job: cancelled });
    } catch (err) {
      setError((err as Error).message);
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
      setPreparationPreview((current) => (current?.arch === arch ? null : current));
      setArchUploads((current) => ({ ...current, [arch]: EMPTY_UPLOAD }));
      setFileInputKeys((current) => ({ ...current, [arch]: current[arch] + 1 }));
      setPipelineDiagnostic(null);
      setDentalIntelligence(null);
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
        if (status.stage_status !== "PROCESSING") stopBusy();
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
      const intelligence = await api.getDentalIntelligence(activeCase.id).catch(() => null);
      if (intelligence) setDentalIntelligence(intelligence);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      stopBusy();
    }
  }

  const workspaceLabel = workflowLabel(workspace);
  const canShowScene = activeReviewStage !== null;
  const showStageTimeline =
    (workspace === "staging" || workspace === "refinement") && treatmentAvailable;

  function requestNewCase(): void {
    if (activeCase) {
      setConfirmNewCaseOpen(true);
      return;
    }
    void handleCreateCase();
  }

  function focusScanInput(which: "upper" | "lower"): void {
    setWorkspace("case-intake");
    window.requestAnimationFrame(() => {
      document.getElementById(which === "lower" ? "lower-stl" : "upper-stl")?.focus();
    });
  }

  async function handleCancelProcessing(): Promise<void> {
    if (!activeCase) return;
    try {
      const status = await api.cancelProcessing(activeCase.id);
      setProcessingStatus(status);
      stopBusy();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function handleNextAction(action: NextAction): void {
    if (action.id === "create-case") {
      requestNewCase();
      return;
    }
    if (action.id === "import-scans") {
      focusScanInput(action.label.includes("lower") && !action.label.includes("upper") ? "lower" : "upper");
      return;
    }
    if (action.id === "resolve-segmentation-environment" || action.id === "review-unresolved") {
      setWorkspace("analysis");
      return;
    }
    if (action.id === "review-segmentation" || action.id === "retry-segmentation") {
      void handleReviewSegmentation();
      return;
    }
    if (action.id === "review-treatment-dependency" || action.id === "open-treatment-plan") {
      setDependencyNotice(null);
      setWorkspace("treatment-setup");
      return;
    }
    if (action.id === "create-treatment-plan") {
      void handleGeneratePlan();
      return;
    }
    if (action.id === "open-staging") {
      setWorkspace("staging");
      return;
    }
    if (action.id === "regenerate-staging") {
      setWorkspace("staging");
      void handleRegenerateStaging();
      return;
    }
    if (action.id === "refresh-validation") {
      setWorkspace("staging");
      void handleRecalculate();
      return;
    }
    if (action.id === "review-findings") {
      setWorkspace("validation");
      return;
    }
    if (action.id === "review-production") {
      setWorkspace("production");
      return;
    }
    if (action.id === "export-package") {
      void handleExportRequest();
      return;
    }
    if (action.id === "cancel-processing") {
      void handleCancelProcessing();
    }
  }

  function issueCamera(command: CameraCommand): void {
    setCameraCommand({ nonce: Date.now(), command });
  }

  function handleTool(id: string): void {
    if (id === "fit-case") issueCamera({ type: "fit-case" });
    else if (id === "fit-arch") {
      issueCamera({ type: "fit-arch", arch: archMode === "lower" ? "lower" : "upper" });
    } else if (id === "fit-selection") {
      const keys = [
        ...(selectedTooth ? [selectedTooth] : []),
        ...multiSelectedKeys.filter((key) => key !== selectedTooth),
      ];
      if (keys.length > 0) issueCamera({ type: "fit-selection", keys });
    } else if (id === "view-occlusal") issueCamera({ type: "preset", preset: "occlusal" });
    else if (id === "view-front") issueCamera({ type: "preset", preset: "front" });
    else if (id === "view-lateral") issueCamera({ type: "preset", preset: "right" });
    else if (id === "reset-view") issueCamera({ type: "reset" });
    else if (id === "arch-upper") setArchMode("upper");
    else if (id === "arch-lower") setArchMode("lower");
    else if (id === "arch-both") setArchMode("both");
    else if (id === "labels") setLabelMode((mode) => nextLabelMode(mode));
    else if (id === "gingiva") setShowGingiva((value) => !value);
    else if (id === "segmentation") setShowSegmentation((value) => !value);
    else if (id === "wireframe") setWireframe((value) => !value);
    else if (id === "movement") setShowMovementVectors((value) => !value);
    else if (id === "target") setShowTargetGhost((value) => !value);
    else if (id === "isolate") setIsolateSelectedTooth((value) => !value);
    else if (id === "undo" && viewportCommandMutatesClinicalState(id)) void handleUndo();
    else if (id === "redo" && viewportCommandMutatesClinicalState(id)) void handleRedo();
    else if (id === "cancel-processing") void handleCancelProcessing();
    else if (id === "retry-segmentation") void handleReviewSegmentation();
    else if (id === "regenerate-staging") void handleRegenerateStaging();
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTextEntryTarget(event.target)) return;
      const shortcut = matchWorkspaceShortcut(event);
      if (!shortcut) return;
      if (shortcut === "delete") {
        deleteShortcutEffect();
        return;
      }
      const command = commandIdForShortcut(shortcut);
      if (!command) return;
      event.preventDefault();
      if (command === "clear-selection") handleClearSelection();
      else handleTool(command);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const reviewTeeth = pipelineReviewStage?.teeth ?? activeReviewStage?.teeth ?? [];
  const segmentationReview = buildSegmentationReviewModel({
    diagnostic: pipelineDiagnostic,
    teeth: reviewTeeth,
    patientReference: activeCase?.patient_reference ?? patientReference,
  });
  const dentalEntries = buildDentalMapEntries(reviewTeeth);
  const selectedMapKeys = [
    ...(selectedTooth ? [selectedTooth] : []),
    ...multiSelectedKeys.filter((key) => key !== selectedTooth),
  ];
  const selectedReviewTooth = reviewTeeth.find((tooth) => toothReviewLabel(tooth).toothRef === selectedTooth) ?? null;
  const selectedReviewLabel = selectedReviewTooth ? toothReviewLabel(selectedReviewTooth) : null;
  const feedback = buildFeedbackModel({
    stageStatus: processingStatus?.stage_status ?? null,
    userMessage: processingStatus?.user_message ?? null,
    elapsedSeconds: processingStatus?.elapsed_seconds ?? null,
    errorCode: processingStatus?.error_code ?? null,
    phase: processingStatus?.current_stage ?? null,
    serverProgress:
      processingStatus?.stage_status === "PROCESSING" ? processingStatus.overall_progress : null,
    remainingTime: processingStatus?.remaining_time ?? null,
    segmentation: segmentationReview,
  });
  const selectedEntries = dentalEntries.filter((entry) => selectedMapKeys.includes(entry.toothRef));
  const groupArches = [...new Set(selectedEntries.map((entry) => entry.arch).filter(Boolean))].join(", ");
  const unresolvedFlags = selectedEntries.map((entry) => entry.unresolved);
  const groupIdentity =
    unresolvedFlags.length === 0
      ? null
      : unresolvedFlags.every((flag) => flag === unresolvedFlags[0])
        ? "same"
        : "mixed";
  const stagingFreshnessValue =
    reviewBundle.smartStaging?.meta?.freshness ?? reviewBundle.smartStaging?.freshness ?? null;
  const validationFreshnessValue = reviewBundle.validationCapability?.freshness ?? null;
  const asFreshness = (value: string | null): "stale" | "current" | "unavailable" | null => {
    if (!value) return null;
    if (value === "stale" || value === "current") return value;
    return "unavailable";
  };
  const workflow = resolveWorkflow({
    activeStep: workspace,
    hasCase: Boolean(activeCase),
    upperReady: archUploads.upper.state === "valid",
    lowerReady: archUploads.lower.state === "valid",
    segmentationKind: segmentationReview.kind,
    hasTreatment: treatmentAvailable,
    hasTarget: targetStage !== null,
    stagingFreshness: asFreshness(stagingFreshnessValue),
    stagingCount: treatmentAvailable ? reviewBundle.stages.length : 0,
    validationFreshness: asFreshness(validationFreshnessValue),
    hasValidationRun: reviewBundle.validationCapability != null || reviewBundle.validationSummary != null,
    productionReachable: treatmentAvailable,
    productionLimited: !reviewBundle.productionCad,
    editCount: reviewBundle.editHistory.length,
    isBusy,
    stageStatus: processingStatus?.stage_status ?? null,
    canCancelProcessing: Boolean(activeCase && processingStatus?.job_id),
    canRegenerateStaging: treatmentAvailable,
    canRefreshValidation: treatmentAvailable,
    unresolvedIdentityCount: segmentationReview.countsAvailable
      ? reviewTeeth.filter((tooth) => !toothReviewLabel(tooth).fdiAuthoritative).length
      : null,
  });
  const workflowSteps = workflow.steps;
  const nextAction = workflow.nextAction;
  const activeWorkflowStep = workflowSteps.find((step) => step.current) ?? workflowSteps[0];
  const orientation = workflowOrientation({
    stepLabel: activeWorkflowStep?.state.replaceAll("_", " ") ?? workspaceLabel,
    blockReason: dependencyNotice ?? activeWorkflowStep?.reason ?? activeWorkflowStep?.emptyState.why ?? null,
    next: nextAction,
  });
  const openWorkflowStep = (id: WorkflowStepId): void => {
    const decision = resolveWorkflowNavigation(workflowSteps, id);
    if (decision.intent === "stay") return;
    if (decision.intent === "explain") {
      setDependencyNotice(decision.reason);
      return;
    }
    setDependencyNotice(decision.showDependency ? decision.reason : null);
    setWorkspace(id);
  };
  const validationFindingCount = reviewBundle.validationCapability
    ? reviewBundle.validationCapability.summary.finding_count
    : reviewBundle.validationSummary
      ? reviewBundle.validationSummary.findings.length
      : null;
  const validationDataAvailable = reviewBundle.validationCapability != null || reviewBundle.validationSummary != null;
  const intakeReadiness = buildCaseIntakeReadiness({
    hasCase: Boolean(activeCase),
    upperState: archUploads.upper.state,
    lowerState: archUploads.lower.state,
  });
  const selectedMeshes = reviewTeeth.filter((tooth) =>
    selectedMapKeys.includes(toothReviewLabel(tooth).toothRef),
  );
  const editableFlags = selectedMeshes.map((tooth) => {
    if (!treatmentAvailable || !tooth.movement) return false;
    return !tooth.movement.locked && !tooth.movement.excluded;
  });
  const groupEditable =
    selectedMapKeys.length < 2
      ? null
      : editableFlags.every(Boolean)
        ? "all"
        : editableFlags.some(Boolean)
          ? "mixed"
          : "none";
  const formatStoredMovement = (
    movement: { translationX: number; translationY: number; translationZ: number; rotation: number } | null | undefined,
  ): string | null => {
    if (!movement) return null;
    return `${movement.translationX.toFixed(2)} ${movement.translationY.toFixed(2)} ${movement.translationZ.toFixed(2)} mm · ${movement.rotation.toFixed(2)}°`;
  };
  const currentMovement = draftMovement ?? selectedFixtureTooth?.movement ?? null;
  const targetMovement = treatmentAvailable ? (currentProposalTooth?.movement ?? null) : null;
  const oneToothEditing =
    selectedMapKeys.length === 1 &&
    (workspace === "treatment-setup" || workspace === "refinement") &&
    treatmentAvailable;
  const inspectorModel = buildInspectorModel({
    minimized: inspectorMinimized,
    patientReference: activeCase?.patient_reference ?? patientReference,
    caseId: activeCase?.id ?? null,
    segmentation: segmentationReview,
    selected: selectedMapKeys.length === 1 ? selectedReviewLabel : null,
    selectionCount: selectedMapKeys.length,
    confidence: selectedReviewTooth?.confidence ?? null,
    treatmentAvailable,
    operation: feedback.state,
    phase: processingStatus?.current_stage ?? null,
    groupArches: groupArches || null,
    groupIdentity,
    groupEditable,
    workspace,
    elapsedLabel: feedback.elapsedLabel,
    serverProgressLabel:
      processingStatus?.stage_status === "PROCESSING" &&
      typeof processingStatus.overall_progress === "number" &&
      Number.isFinite(processingStatus.overall_progress)
        ? `Server reported ${Math.round(processingStatus.overall_progress)}`
        : null,
    failureMessage:
      feedback.state === "failed" ? (processingStatus?.user_message?.trim() || null) : null,
    transform:
      selectedMapKeys.length === 1
        ? {
            current: formatStoredMovement(currentMovement),
            target: formatStoredMovement(targetMovement),
            locked: draftMovement ? Boolean(draftMovement.locked) : null,
            excluded: draftMovement ? Boolean(draftMovement.excluded) : null,
            editable: oneToothEditing ? canTransformTooth(draftMovement) : null,
          }
        : null,
    facts: {
      readiness: intakeReadiness.completenessLabel,
      nextAction: nextAction?.label ?? null,
      version: reviewBundle.versionId ? reviewBundle.versionId.slice(0, 12) : null,
      savedVersions: reviewBundle.treatmentSetup?.versions.length ?? null,
      stale: asFreshness(stagingFreshnessValue) === "stale",
      limits: treatmentAvailable ? "No movement limits are configured" : null,
      stageCount: treatmentAvailable ? reviewBundle.stages.length : null,
      stageIndex: treatmentAvailable ? stageIndex : null,
      freshness:
        workspace === "validation"
          ? validationFreshnessValue
          : stagingFreshnessValue,
      editCount: reviewBundle.editHistory.length,
      findingCount: validationFindingCount,
      unavailableChecks: reviewBundle.validationCapability?.summary.unavailable_checks ?? null,
      truth:
        workspace === "production"
          ? (reviewBundle.productionCad?.overall_truth_state ?? null)
          : (reviewBundle.validationCapability?.overall_truth_state ?? null),
      severity: reviewBundle.validationCapability?.overall_check_state ?? null,
      source: reviewBundle.productionCad?.binding.source_kind ?? null,
      qc: reviewBundle.productionCad?.export_state ?? null,
      preparation:
        (["upper", "lower"] as const)
          .flatMap((arch) => {
            if (archUploads[arch].state === "empty") return [];
            const readiness = archUploads[arch].intake?.preparation?.readiness ?? "NOT_PREPARED";
            return [`${arch} ${readiness}`];
          })
          .join(" · ") || null,
      preparationJob: preparationJob
        ? [
            preparationJob.arch,
            preparationJob.job.operation ?? "preparation",
            preparationJob.job.state ?? "queued",
            typeof preparationJob.job.progress === "number"
              ? `${Math.round(preparationJob.job.progress * 100)}%`
              : null,
            typeof preparationJob.job.duration_ms === "number"
              ? `${Math.round(preparationJob.job.duration_ms)} ms`
              : null,
          ]
            .filter(Boolean)
            .join(" ")
        : null,
      segmentation: (["upper", "lower"] as const)
        .flatMap((arch) => {
          const record = archUploads[arch].intake?.segmentation;
          if (!record?.capability_state && !record?.active_run && !segmentationJob) return [];
          const state = record?.availability ?? record?.capability_state ?? segmentationJob?.job.state;
          return state ? [`${arch} ${state}`] : [];
        })
        .join(" · ") || (segmentationJob ? `${segmentationJob.arch} ${segmentationJob.job.state ?? "queued"}` : null),
      segmentationIdentity: (["upper", "lower"] as const)
        .map((arch) => archUploads[arch].intake?.segmentation?.semantic_identity)
        .find(Boolean) ?? (segmentationJob ? "NOT_ESTABLISHED" : null),
    },
    productionNote: reviewBundle.productionCad
      ? reviewBundle.productionCad.overall_truth_state.replaceAll("_", " ")
      : treatmentAvailable
        ? "Manufacturing capabilities are not available"
        : null,
  });
  const toolbar = resolveToolbar({
    workspace,
    hasCase: Boolean(activeCase),
    sceneAvailable: canShowScene,
    segmentationKind: segmentationReview.kind,
    selectionCount: selectedMapKeys.length,
    groupIdentity,
    archMode,
    isolateActive: isolateSelectedTooth,
    labelMode,
    gingivaVisible: showGingiva,
    segmentationVisible: showSegmentation,
    wireframe,
    movementVisible: showMovementVectors,
    targetVisible: showTargetGhost,
    treatmentAvailable,
    targetGeometryExists: targetStage !== null,
    validationAvailable: validationDataAvailable || validation != null,
    validationFindingCount: validationFindingCount != null && validationFindingCount > 0 ? validationFindingCount : null,
    stagingCount: treatmentAvailable ? reviewBundle.stages.length : 0,
    stagingStale: asFreshness(stagingFreshnessValue) === "stale",
    canTransform: treatmentAvailable && canTransformTooth(draftMovement),
    canUndo: undoStack.length > 0,
    canRedo: redoStack.length > 0,
    canCancelProcessing: Boolean(activeCase && processingStatus?.job_id && processingStatus.stage_status === "PROCESSING"),
    canRetrySegmentation:
      segmentationReview.kind === "failed" ||
      processingStatus?.stage_status === "CANCELLED" ||
      processingStatus?.stage_status === "INTERRUPTED",
    commitOwnedByInspector: oneToothEditing,
    canRegenerateStaging: treatmentAvailable,
    stageStatus: processingStatus?.stage_status ?? null,
    suppressedIds: [
      ...(nextAction ? [nextAction.id] : []),
      ...(workspace === "staging" ? ["regenerate-staging"] : []),
      ...(loadingPresentation ? ["cancel-processing"] : []),
    ],
    manipulationOwnedByToothToolbar: Boolean(
      selectedTooth && (workspace === "treatment-setup" || workspace === "refinement"),
    ),
  });
  const widgets = resolveWidgets({
    selectionCount: selectedMapKeys.length,
    selectionLabel: selectedReviewLabel?.text ?? null,
    selectionArch: selectedReviewLabel?.arch ?? null,
    groupArches: groupArches || null,
    groupIdentity,
    identityUnresolved: selectedReviewLabel ? !selectedReviewLabel.fdiAuthoritative : unresolvedFlags.some(Boolean),
    fixture: Boolean(selectedReviewLabel?.fixture || segmentationReview.kind === "fixture_test_only" || reviewBundle.fixture),
    provenanceLabel: segmentationReview.provenanceLabel || null,
    provenanceStripVisible: workspace === "analysis" || Boolean(pipelineDiagnostic),
    processing: processingStatus?.stage_status === "PROCESSING",
    processingOwnedByStatus: Boolean(loadingPresentation),
    phase: processingStatus?.current_stage ?? null,
    elapsedLabel: feedback.elapsedLabel,
    serverProgress:
      typeof processingStatus?.overall_progress === "number" ? processingStatus.overall_progress : null,
    canCancel: Boolean(processingStatus?.job_id),
    targetGeometryExists: targetStage !== null,
    showTarget: showTargetGhost,
    showCurrent: true,
    stagingCount: treatmentAvailable ? reviewBundle.stages.length : 0,
    stagingIndex: treatmentAvailable ? stageIndex : null,
    stagingStale: asFreshness(stagingFreshnessValue) === "stale",
    stagingTimelineVisible: showStageTimeline,
    validationAvailable: validationDataAvailable,
    validationFindingCount: validationFindingCount != null && validationFindingCount > 0 ? validationFindingCount : null,
    validationPanelVisible: workspace === "validation",
    dependencyText: orientation.now,
    orientationVisible: true,
  });
  const toolbarTools = toolbar.primary.map((item) => ({
    id: item.id,
    label: item.label,
    available: item.executable,
    reason: item.reason,
    shortcut: item.shortcut,
    active: item.active,
    availability: item.availability,
  }));
  const toolbarMore = toolbar.more.map((item) => ({
    id: item.id,
    label: item.label,
    available: item.executable,
    reason: item.reason,
    shortcut: item.shortcut,
    active: item.active,
    availability: item.availability,
  }));
  const toolbarWithheld = toolbar.withheld.map((item) => ({
    id: item.id,
    label: item.label,
    reason: item.reason,
    availability: item.availability === "available" ? ("unavailable" as const) : item.availability,
  }));
  const inlineError = dedupeNotice(feedback.whatHappened, error);
  const transientNotice = dedupeNotice(feedback.whatHappened, dedupeNotice(inlineError, exportMessage));
  const inspectorIsMinimized = inspectorMinimized;

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
            const environmentBlocked = id === "analysis" && segmentationReview.kind === "blocked_by_environment";
            const mark = step.satisfied ? "✓" : String(index + 1).padStart(2, "0");
            return (
              <button
                className={`cad-workflow-step is-${step.state} ${step.current ? "is-current" : ""}${environmentBlocked ? " is-environment-blocked" : ""}`}
                key={id}
                type="button"
                data-testid={`workflow-step-${id}`}
                data-step-visual={environmentBlocked ? "environment" : step.state}
                data-workflow-state={step.state}
                data-navigation={step.navigationAllowed ? "allowed" : "explain"}
                onClick={() => openWorkflowStep(id)}
                aria-current={step.current ? "step" : undefined}
                title={step.reason ?? step.label}
              >
                <span>{mark}</span>
                {step.label}
              </button>
            );
          })}
        </nav>
        <div className="cad-environment">
          {nextAction?.showInHeader ? (
            <button
              type="button"
              className="primary-button"
              data-testid="header-next-action"
              data-next-action={nextAction.id}
              title={nextAction.reason}
              onClick={() => handleNextAction(nextAction)}
            >
              {nextAction.label}
            </button>
          ) : null}
          <PrimaryStatus feedback={feedback} compact={Boolean(loadingPresentation)} />
          {transientNotice ? (
            <span className="transient-notice" data-testid="transient-notice">
              {transientNotice}
            </span>
          ) : null}
        </div>
      </WorkflowHeader>

      <WorkspaceContainer className={inspectorIsMinimized ? "is-inspector-minimized" : ""}>
        <LeftToolPanel>
          <div className="cad-panel-heading">
            <div>
              <span className="eyebrow">Workflow</span>
              <h2>{workspaceLabel}</h2>
            </div>
            <span className="panel-index">{String(workflowStepIndex(workspace) + 1).padStart(2, "0")}</span>
          </div>
          <section
            className="workflow-step-brief"
            data-testid="workflow-step-brief"
            data-workflow-state={activeWorkflowStep?.state ?? "not_started"}
            data-canonical-next-action={nextAction?.id ?? "none"}
          >
            <WorkflowOrientation where={orientation.where} now={orientation.now} next={orientation.next} />
          </section>
          {workspace !== "case-intake" && activeCase && (
            <div className="cad-quick-actions">
              <button
                className="text-button"
                onClick={() => setWorkspace("case-intake")}
                data-testid="goto-case-intake"
              >
                Case
              </button>
            </div>
          )}

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
              segmentationReviewed={pipelineReviewStage !== null}
              onCreateCase={() => void handleCreateCase()}
              onRequestNewCase={requestNewCase}
              onUpload={(arch, file) => void handleUploadAndValidate(arch, file)}
              onRemoveMesh={(arch) => void handleRemoveMesh(arch)}
              onAnalyzeCase={() => void handleReviewSegmentation()}
              onReviewTreatmentProposal={() => void handleGeneratePlan()}
              onOpenTreatmentPlan={() => {
                setDependencyNotice(null);
                setWorkspace("treatment-setup");
              }}
              primaryActionId={nextAction?.id ?? null}
              preparationPreview={preparationPreview}
              preparationJob={preparationJob}
              onPrepare={(arch, request) => void handlePrepare(arch, request)}
              onDismissPreview={() => setPreparationPreview(null)}
              onCancelPreparationJob={() => void handleCancelPreparationJob()}
              segmentationJob={segmentationJob}
              onStartSegmentation={(arch) => void handleStartSegmentation(arch)}
              onReviewSegmentation={(arch, request) => void handleSegmentationReview(arch, request)}
            />
          )}
          {workspace === "analysis" && (
            <AnalysisPanel
              bothArchesValid={bothArchesValid}
              diagnostic={pipelineDiagnostic}
              dentalIntelligence={dentalIntelligence}
              teeth={pipelineReviewStage?.teeth ?? []}
              validation={validation}
              hiddenToothIds={hiddenToothIds}
              onAnalyzeCase={() => void handleReviewSegmentation()}
              runBlocked={segmentationReview.kind === "blocked_by_environment"}
              fixtureOnly={segmentationReview.kind === "fixture_test_only"}
              emphasizeRun={
                nextAction?.id === "review-segmentation" || nextAction?.id === "retry-segmentation"
              }
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
              versionCompare={versionCompare}
              onGeneratePlan={() => void handleGeneratePlan()}
              emphasizeCreate={nextAction?.id === "create-treatment-plan"}
              onToggleInitialPosition={setShowOriginal}
              onToggleTargetPosition={setShowTargetGhost}
              onOriginalOpacityChange={setOriginalOpacity}
              onSelectAlternative={(alternativeId) =>
                void handleSelectSetupAlternative(alternativeId)
              }
              onSaveVersion={(description) => void handleSaveSetupVersion(description)}
              onRestoreVersion={(versionId) => void handleRestoreSetupVersion(versionId)}
              onCompareVersions={(left, right) => void handleCompareSetupVersions(left, right)}
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
              smartStaging={reviewBundle.smartStaging}
              onSelectStage={(index) => {
                setStageIndex(index);
                setIsPlaying(false);
              }}
              onTogglePlay={() => setIsPlaying((playing) => !playing)}
              onShowUpper={setShowUpper}
              onShowLower={setShowLower}
              onShowMovementVectors={setShowMovementVectors}
              onRecalculate={() => void handleRecalculate()}
              onRegenerateStaging={() => void handleRegenerateStaging()}
              onSaveStagingVersion={() => void handleSaveStagingVersion()}
            />
          )}

          {workspace === "refinement" && (
            <RefinementPanel bundle={reviewBundle} treatmentAvailable={treatmentAvailable} />
          )}

          {workspace === "validation" && (
            <ValidationWorkflowPanel bundle={reviewBundle} stage={activeReviewStage} />
          )}

          {workspace === "production" && (
            <ProductionPanel
              bundle={reviewBundle}
              treatmentAvailable={treatmentAvailable}
              onExport={() => void handleExportRequest()}
              onSelectProductionSource={(stageIndex, sourceKind) => {
                if (!activeCase?.id) return;
                void api
                  .selectProductionSource(activeCase.id, {
                    stage_index: stageIndex,
                    source_kind: sourceKind,
                  })
                  .then((bundle) => setReviewBundle(bundle))
                  .catch(() => undefined);
              }}
            />
          )}

          {import.meta.env.MODE === "test" && (
            <button
              className="production-test-hook"
              aria-label="Load engineering demo"
              onClick={() => void handleLoadEngineeringDemo()}
            />
          )}

          {inlineError && (
            <div className="error-message" data-testid="inline-error">
              {inlineError}
            </div>
          )}
        </LeftToolPanel>

        <section className="cad-viewport-column" data-testid="layout-viewport">
          <div className="cad-viewport-header">
            <div>
              <span className="eyebrow">{workspace === "analysis" ? "Analysis" : workspaceLabel}</span>
              <h1>{workspace === "analysis" ? "Segmentation Review" : workspaceLabel}</h1>
            </div>
            <SmartWidgets models={widgets} />
          </div>
          {workspace === "analysis" || pipelineDiagnostic ? (
            <SegmentationReviewStrip
              model={segmentationReview}
              patientReference={activeCase?.patient_reference ?? patientReference}
              compact
            />
          ) : null}
          <div className="cad-viewport-frame">
            {(workspace === "analysis" || dentalEntries.length > 0 || segmentationReview.kind !== "not_run") ? (
            <DentalArchMap
              entries={dentalEntries}
              kind={segmentationReview.kind}
              selectedKeys={selectedMapKeys}
              hoveredKey={hoveredToothKey}
              onSelect={(toothRef, additive) => handleSelectTooth(toothRef, { additive })}
              onHover={setHoveredToothKey}
            />
            ) : null}
            {canShowScene && sceneGraph ? (
              <StageViewer
                stage={activeReviewStage}
                sceneGraph={sceneGraph}
                targetStage={targetStage}
                selectedTooth={selectedTooth}
                multiSelectedTeeth={multiSelectedKeys}
                showUpper={showUpper}
                showLower={showLower}
                isolatedArch={isolatedArch}
                isolatedToothKey={isolatedToothKey}
                showOriginal={showOriginal}
                originalOpacity={originalOpacity}
                wireframe={wireframe}
                hiddenToothIds={hiddenToothIds}
                gizmoMode={gizmoMode}
                onGizmoMovement={handleGizmoMovement}
                transformEnabled={
                  treatmentAvailable && canTransformTooth(draftMovement)
                }
                onSelectTooth={handleSelectTooth}
                onClearSelection={handleClearSelection}
                onHoverTooth={setHoveredToothKey}
                hoveredToothKey={hoveredToothKey}
                cameraCommand={cameraCommand}
                labelMode={labelMode}
                showBuiltinCameraTools={false}
                onFit={() => undefined}
                onReset={() => undefined}
                contextualToolbar={
                  <ContextualWorkspaceToolbar
                    context={toolbar.context}
                    tools={toolbarTools}
                    advanced={toolbarMore}
                    unavailable={toolbarWithheld}
                    onTool={handleTool}
                    extra={
                      selectedTooth && (workspace === "treatment-setup" || workspace === "refinement") ? (
                        <ContextualToothToolbar
                          embedded
                          label={selectedReviewLabel?.text ?? selectedTooth}
                          arch={selection.arch}
                          gizmoMode={gizmoMode}
                          onGizmoMode={setGizmoMode}
                          canEdit={treatmentAvailable && draftMovement !== null}
                          canTransform={canTransformTooth(draftMovement)}
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
                          commitOwnedByInspector
                        />
                      ) : null
                    }
                  />
                }
              />
            ) : (
              <>
              <ContextualWorkspaceToolbar
                context={toolbar.context}
                tools={toolbarTools}
                advanced={toolbarMore}
                unavailable={toolbarWithheld}
                onTool={handleTool}
              />
              <ProductionEmptyState
                title={
                  segmentationReview.kind === "blocked_by_environment"
                    ? "Segmentation blocked"
                    : segmentationReview.kind === "failed"
                      ? "Segmentation failed"
                      : segmentationReview.kind === "not_available"
                        ? "Segmentation not available"
                        : segmentationReview.kind === "fixture_test_only"
                          ? "Fixture geometry only"
                          : activeCase
                            ? "No tooth surfaces yet"
                            : "Prepare a case to begin"
                }
                detail={
                  segmentationReview.kind === "not_run"
                    ? (reviewBundle.unavailableReason ??
                      "Import upper and lower scans to establish the dental workspace.")
                    : segmentationReview.whatHappened
                }
                action={
                  workspace !== "case-intake" && segmentationReview.kind === "not_run" ? (
                    <button
                      className="secondary-button"
                      onClick={() => setWorkspace("case-intake")}
                    >
                      Go to Case Intake
                    </button>
                  ) : undefined
                }
              />
              </>
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
          <AdaptiveInspector
            model={inspectorModel}
            minimized={inspectorIsMinimized}
            onToggle={() => setInspectorMinimized((value) => !value)}
          />
          {inspectorIsMinimized ? null : (
            <>
              {oneToothEditing && selectedFixtureTooth ? (
                <InspectionPanel
                  tooth={selectedFixtureTooth}
                  dentalIntelligence={dentalIntelligence}
                  draftMovement={draftMovement}
                  originalMovement={
                    workspace === "refinement"
                      ? (originalTooth?.movement ?? null)
                      : (currentProposalTooth?.movement ?? null)
                  }
                  isDirty={
                    draftMovement !== null &&
                    currentProposalTooth !== null &&
                    hasMovementChanges(draftMovement, currentProposalTooth.movement)
                  }
                  onDraftChange={handleDraftChange}
                  interactionState={toothInteractionState}
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
                  embedded
                />
              ) : null}
              {workspace === "refinement" && treatmentAvailable ? (
                <div className="cad-inspector-section">
                  <button
                    className="secondary-button"
                    onClick={handleResetAll}
                    disabled={reviewBundle.editHistory.length === 0}
                  >
                    Reset all edits
                  </button>
                </div>
              ) : null}
              {workspace === "refinement" ? (
                <details className="inspector-review-fold" data-testid="refinement-review-fold">
                  <summary>
                    IPR and attachment review
                    {reviewBundle.iprSites.length + reviewBundle.attachmentSites.length > 0
                      ? ` (${reviewBundle.iprSites.length + reviewBundle.attachmentSites.length})`
                      : ""}
                    . Review candidates, not prescriptions.
                  </summary>
                  <ProposalPanels
                    iprSites={reviewBundle.iprSites}
                    attachmentSites={reviewBundle.attachmentSites}
                    clinicalToolsFreshness={reviewBundle.clinicalTools?.freshness}
                    clinicalToolsNotes={reviewBundle.clinicalTools?.notes}
                    onIPRStatus={(siteId, status) => void handleIPRStatus(siteId, status)}
                    onIPRAmount={(siteId, amount) => void handleIPRAmount(siteId, amount)}
                    onAttachmentStatus={(siteId, status) =>
                      void handleAttachmentStatus(siteId, status)
                    }
                    onReset={() => void handleResetProposals()}
                  />
                </details>
              ) : null}
              {workspace === "validation" && activeReviewStage ? (
                <ValidationPanel stage={activeReviewStage} bundle={reviewBundle} />
              ) : null}
            </>
          )}
        </RightInspector>
      </WorkspaceContainer>
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
      {loadingPresentation ? (
        <CaseLoadingOverlay
          presentation={loadingPresentation}
          onCancel={
            processingStatus?.stage_status === "PROCESSING" && processingStatus.job_id
              ? () => void handleCancelProcessing()
              : undefined
          }
        />
      ) : null}
      <ConfirmDialog
        open={confirmNewCaseOpen}
        title="Start another case?"
        message="The current case stays in the session until you create a new one. Unsaved viewport edits may be cleared."
        confirmLabel="Create new case"
        cancelLabel="Cancel"
        onCancel={() => setConfirmNewCaseOpen(false)}
        onConfirm={() => {
          setConfirmNewCaseOpen(false);
          void handleCreateCase();
        }}
      />
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
