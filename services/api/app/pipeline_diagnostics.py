"""Engineering-only diagnostics for uploaded-case processing; no fixture fallback."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from time import perf_counter

from domain.tooth.identification import ArchType
from engines.arrangement.anatomical_intelligence import (
    build_anatomical_intelligence_summary,
    serialize_arch_measurements,
    serialize_identified_tooth,
)
from engines.arrangement.arch_analysis import ArchAnalysisEngine, ArchAnalysisError

from app.toothinstancenet_configuration import (
    ToothInstanceNetConfigurationError,
    load_validated_fixture_result,
    selected_backend,
)


class PipelineState(StrEnum):
    MODEL_UNAVAILABLE = "model_unavailable"
    BLOCKED_BY_ENVIRONMENT = "blocked_by_environment"
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
    provenance: str = "experimental"
    fixture: bool = False
    experimental: bool = True
    fdi_assignments: tuple[tuple[int, int | None], ...] = ()
    duplicate_fdi_numbers: tuple[int, ...] = ()
    missing_fdi_numbers: tuple[int, ...] = ()
    excluded_fragment_count: int = 0
    tooth_instances: tuple[dict, ...] = ()
    arch_measurements: dict | None = None
    anatomical_intelligence: dict | None = None
    # WP-01 provenance binding — present on real uploads; absent on legacy calls.
    processing_mode: str | None = None
    case_id: str | None = None
    job_id: str | None = None
    input_hash: str | None = None
    source_mesh_path: str | None = None
    source_mesh_sha256: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    arch: str | None = None
    backend: str | None = None
    segmentation_truth_state: str | None = None
    runtime_blocker: str | None = None
    recoverable: bool | None = None
    preprocessing: dict | None = None
    runtime: dict | None = None
    limitations: tuple[str, ...] = ()
    segmentation_contract: dict | None = None
    timings_ms: dict | None = None

    def payload(self) -> dict:
        return {**asdict(self), "state": self.state.value}


def process_uploaded_case(
    mesh_path: str,
    arch: ArchType,
    *,
    case_id: str | None = None,
    job_id: str | None = None,
    input_hash: str | None = None,
    processing_mode: str | None = None,
) -> CasePipelineDiagnostic:
    """Route uploaded-case processing across the REAL / TEST_FIXTURE boundary.

    Production real-case calls must never silently load fixture geometry.
    """
    from app.processing_modes import (
        ProcessingMode,
        ProcessingModeError,
        resolve_processing_mode,
    )
    from app.real_case_pipeline import process_real_uploaded_arch

    started = perf_counter()
    try:
        mode = (
            ProcessingMode(processing_mode)
            if processing_mode
            else resolve_processing_mode()
        )
    except ProcessingModeError as error:
        return _diagnostic(
            PipelineState.MODEL_UNAVAILABLE,
            started,
            failures=(str(error),),
            source_kind="uploaded_real_case",
            fixture=False,
            notes=("Fixture backend blocked for real-case processing.",),
            processing_mode=ProcessingMode.REAL_CASE.value,
            case_id=case_id,
            job_id=job_id,
            input_hash=input_hash,
            source_mesh_path=mesh_path,
        )
    except ValueError:
        mode = resolve_processing_mode()

    if mode is ProcessingMode.REAL_CASE:
        return process_real_uploaded_arch(
            mesh_path,
            arch,
            case_id=case_id,
            job_id=job_id,
            input_hash=input_hash,
        )

    # Explicit test-fixture path only.
    backend = selected_backend()
    if backend != "toothinstancenet_fixture":
        return _diagnostic(
            PipelineState.MODEL_UNAVAILABLE,
            started,
            failures=(f"Unsupported test fixture backend: {backend}",),
            fixture=False,
        )
    try:
        result = load_validated_fixture_result(arch, mesh_path)
    except ToothInstanceNetConfigurationError as error:
        return _diagnostic(PipelineState.MODEL_UNAVAILABLE, started, failures=(str(error),))
    except Exception as error:
        return _diagnostic(PipelineState.SEGMENTATION_FAILED, started, failures=(str(error),))
    diagnostic = _diagnostic_from_result(result, started, source_kind="validated_real_case")
    return CasePipelineDiagnostic(
        **{
            **diagnostic.__dict__,
            "processing_mode": ProcessingMode.TEST_FIXTURE.value,
            "case_id": case_id,
            "job_id": job_id,
            "input_hash": input_hash,
            "source_mesh_path": mesh_path,
            "fixture": True,
            "model_name": result.segmentation.metadata.model_name,
            "model_version": result.segmentation.metadata.model_version,
        }
    )


def _diagnostic(state: PipelineState, started: float, **values) -> CasePipelineDiagnostic:
    return CasePipelineDiagnostic(
        state=state,
        source_kind=values.get("source_kind", "uploaded_real_case"),
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
        provenance=values.get("provenance", "experimental"),
        fixture=values.get("fixture", False),
        experimental=values.get("experimental", True),
        fdi_assignments=values.get("fdi_assignments", ()),
        duplicate_fdi_numbers=values.get("duplicate_fdi_numbers", ()),
        missing_fdi_numbers=values.get("missing_fdi_numbers", ()),
        excluded_fragment_count=values.get("excluded_fragment_count", 0),
        tooth_instances=values.get("tooth_instances", ()),
        arch_measurements=values.get("arch_measurements"),
        anatomical_intelligence=values.get("anatomical_intelligence"),
        processing_mode=values.get("processing_mode"),
        case_id=values.get("case_id"),
        job_id=values.get("job_id"),
        input_hash=values.get("input_hash"),
        source_mesh_path=values.get("source_mesh_path"),
        source_mesh_sha256=values.get("source_mesh_sha256"),
        model_name=values.get("model_name"),
        model_version=values.get("model_version"),
        arch=values.get("arch"),
        backend=values.get("backend"),
        segmentation_truth_state=values.get("segmentation_truth_state"),
        runtime_blocker=values.get("runtime_blocker"),
        recoverable=values.get("recoverable"),
        preprocessing=values.get("preprocessing"),
        runtime=values.get("runtime"),
        limitations=values.get("limitations", ()),
        segmentation_contract=values.get("segmentation_contract"),
        timings_ms=values.get("timings_ms"),
    )


def _diagnostic_from_result(result, started: float, *, source_kind: str):
    identification = result.identification
    scores = [item.confidence.score for item in identification.teeth]
    tooth_instances = tuple(
        {
            **serialize_identified_tooth(tooth),
            "arch": identification.arch.value,
            "experimental": True,
        }
        for tooth in identification.teeth
    )
    arch_measurements = None
    fully_identified = (
        identification.identified
        and not identification.uncertain
        and not identification.unidentified
    )
    if fully_identified:
        try:
            arch_measurements = ArchAnalysisEngine().analyze(identification)
        except ArchAnalysisError:
            arch_measurements = None
    # Semantic-only fixtures typically lack landmarks; arch analysis stays unavailable.
    summary = build_anatomical_intelligence_summary(
        identification=identification,
        arch_measurements=arch_measurements,
    )
    base = {
        "segmentation_runtime_ms": (perf_counter() - started) * 1000,
        "tooth_instance_count": len(result.segmentation.instances),
        "identification_confidence": sum(scores) / len(scores) if scores else None,
        "identified_teeth": len(identification.identified),
        "uncertain_teeth": len(identification.uncertain),
        "unidentified_teeth": len(identification.unidentified),
        "provenance": result.segmentation.metadata.provenance.value,
        "fixture": result.segmentation.metadata.fixture,
        "experimental": True,
        "fdi_assignments": result.diagnostics.fdi_by_instance,
        "duplicate_fdi_numbers": result.diagnostics.duplicate_fdi_numbers,
        "missing_fdi_numbers": result.diagnostics.missing_fdi_numbers,
        "excluded_fragment_count": len(result.diagnostics.empty_instance_ids),
        "tooth_instances": tooth_instances,
        "notes": result.diagnostics.notes,
        "arch_analysis_available": arch_measurements is not None,
        "arch_measurements": serialize_arch_measurements(arch_measurements),
        "anatomical_intelligence": summary.payload(),
        "timings_ms": getattr(result, "timings_ms", None),
    }
    state = PipelineState(result.status)
    return _diagnostic(state, started, source_kind=source_kind, **base)
