"""Engineering-only diagnostics for uploaded-case processing; no fixture fallback."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from time import perf_counter

from domain.tooth.identification import ArchType
from engines.arrangement.arch_analysis import ArchAnalysisEngine, ArchAnalysisError
from engines.arrangement.identification import ToothIdentificationEngine
from engines.segmentation.onnx_engine import OnnxSegmentationEngine

from app.segmentation_config import SegmentationConfigurationError, load_segmentation_configuration


class PipelineState(StrEnum):
    MODEL_UNAVAILABLE = "model_unavailable"
    SEGMENTATION_FAILED = "segmentation_failed"
    IDENTIFICATION_INCOMPLETE = "identification_incomplete"
    PLANNING_UNAVAILABLE = "planning_unavailable"
    PLANNING_READY = "planning_ready"


@dataclass(frozen=True)
class CasePipelineDiagnostic:
    state: PipelineState
    source_kind: str
    segmentation_runtime_ms: float | None
    total_runtime_ms: float
    tooth_instance_count: int
    identification_confidence: float | None
    identified_teeth: int
    uncertain_teeth: int
    unidentified_teeth: int
    validation_findings: tuple[str, ...]
    failures: tuple[str, ...]
    arch_analysis_available: bool
    notes: tuple[str, ...]

    def payload(self) -> dict:
        return {**asdict(self), "state": self.state.value}


def process_uploaded_case(mesh_path: str, arch: ArchType) -> CasePipelineDiagnostic:
    """Process a real upload only when a verified external model is configured."""
    started = perf_counter()
    try:
        configuration = load_segmentation_configuration()
    except SegmentationConfigurationError as error:
        return _diagnostic(PipelineState.MODEL_UNAVAILABLE, started, failures=(str(error),))

    try:
        segmented = OnnxSegmentationEngine(adapter=configuration.adapter()).segment(mesh_path)
    except Exception as error:  # model/runtime errors are surfaced as diagnostic state
        return _diagnostic(PipelineState.SEGMENTATION_FAILED, started, failures=(str(error),))

    segmentation_ms = (perf_counter() - started) * 1000
    identification = ToothIdentificationEngine().identify(segmented, arch)
    scores = [item.confidence.score for item in identification.teeth]
    base = {
        "segmentation_runtime_ms": segmentation_ms,
        "tooth_instance_count": len(segmented.instances),
        "identification_confidence": sum(scores) / len(scores) if scores else None,
        "identified_teeth": len(identification.identified),
        "uncertain_teeth": len(identification.uncertain),
        "unidentified_teeth": len(identification.unidentified),
    }
    if identification.uncertain or identification.unidentified:
        return _diagnostic(
            PipelineState.IDENTIFICATION_INCOMPLETE,
            started,
            **base,
            failures=("Identification is incomplete; planning is blocked.",),
        )
    try:
        ArchAnalysisEngine().analyze(identification)
    except ArchAnalysisError as error:
        return _diagnostic(
            PipelineState.IDENTIFICATION_INCOMPLETE, started, **base, failures=(str(error),)
        )
    return _diagnostic(
        PipelineState.PLANNING_READY,
        started,
        **base,
        arch_analysis_available=True,
        notes=(
            "Segmentation and geometric identification completed. Explicit treatment objectives "
            "are still required before setup generation.",
        ),
    )


def _diagnostic(state: PipelineState, started: float, **values) -> CasePipelineDiagnostic:
    return CasePipelineDiagnostic(
        state=state,
        source_kind="uploaded_real_case",
        segmentation_runtime_ms=values.get("segmentation_runtime_ms"),
        total_runtime_ms=(perf_counter() - started) * 1000,
        tooth_instance_count=values.get("tooth_instance_count", 0),
        identification_confidence=values.get("identification_confidence"),
        identified_teeth=values.get("identified_teeth", 0),
        uncertain_teeth=values.get("uncertain_teeth", 0),
        unidentified_teeth=values.get("unidentified_teeth", 0),
        validation_findings=values.get("validation_findings", ()),
        failures=values.get("failures", ()),
        arch_analysis_available=values.get("arch_analysis_available", False),
        notes=values.get("notes", ("Engineering measurements only; no clinical accuracy claim.",)),
    )
