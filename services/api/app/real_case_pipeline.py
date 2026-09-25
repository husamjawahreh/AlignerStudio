"""Real-case segmentation path: uploaded STL → ToothInstanceNet only (WP-01).

Never loads fixture geometry. Failures are returned as honest diagnostic states.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from time import perf_counter

from domain.tooth.identification import ArchType
from engines.arrangement.anatomical_intelligence import (
    build_anatomical_intelligence_summary,
    serialize_arch_measurements,
    serialize_identified_tooth,
)
from engines.arrangement.arch_analysis import ArchAnalysisEngine, ArchAnalysisError
from engines.arrangement.identification import ToothIdentificationEngine
from engines.segmentation.onnx_engine import OnnxSegmentationEngine

from app.pipeline_diagnostics import (
    CasePipelineDiagnostic,
    PipelineState,
    _diagnostic,
    _diagnostic_from_result,
)
from app.processing_modes import ProcessingMode, require_real_case_mode
from app.segmentation_config import SegmentationConfigurationError, load_segmentation_configuration
from app.segmentation_runtime import assess_segmentation_runtime, inspect_uploaded_mesh
from app.toothinstancenet_configuration import (
    ToothInstanceNetConfigurationError,
    load_toothinstancenet_engine,
    selected_backend,
)


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_context(
    *,
    binding: dict,
    arch: ArchType,
    mesh: Path,
    source_sha: str | None,
    assessment: dict,
) -> dict:
    preprocessing = None
    if source_sha and mesh.is_file():
        preprocessing = inspect_uploaded_mesh(mesh, arch=arch.value, source_sha256=source_sha)
    return {
        **binding,
        "arch": arch.value,
        "backend": assessment.get("backend"),
        "runtime": assessment,
        "runtime_blocker": assessment.get("blocker"),
        "recoverable": assessment.get("recoverable"),
        "preprocessing": preprocessing,
        "limitations": (
            "Segmentation did not produce clinical tooth instances.",
        )
        if assessment.get("capability") != "ready"
        else (),
    }


def process_real_uploaded_arch(
    mesh_path: str,
    arch: ArchType,
    *,
    case_id: str | None = None,
    job_id: str | None = None,
    input_hash: str | None = None,
) -> CasePipelineDiagnostic:
    """Process a real uploaded mesh. Fixture backends are rejected at the boundary."""
    require_real_case_mode()
    started = perf_counter()
    mesh = Path(mesh_path)
    binding = {
        "processing_mode": ProcessingMode.REAL_CASE.value,
        "case_id": case_id,
        "job_id": job_id,
        "input_hash": input_hash,
        "source_mesh_path": str(mesh),
        "fixture": False,
        "source_kind": "uploaded_real_case",
    }
    if not mesh.is_file():
        return _diagnostic(
            PipelineState.SEGMENTATION_FAILED,
            started,
            failures=(f"Uploaded mesh is missing: {mesh_path}",),
            segmentation_truth_state="failed",
            arch=arch.value,
            **binding,
        )
    source_sha = _sha256_file(mesh)
    binding["source_mesh_sha256"] = source_sha
    backend = selected_backend()
    assessment = assess_segmentation_runtime()
    context = _source_context(
        binding=binding, arch=arch, mesh=mesh, source_sha=source_sha, assessment=assessment
    )

    if backend == "toothinstancenet":
        try:
            result = load_toothinstancenet_engine(arch).segment(str(mesh))
        except ToothInstanceNetConfigurationError as error:
            blocked = assessment.get("capability") == "blocked_by_environment"
            blocker = assessment.get("blocker") or str(error)
            state = (
                PipelineState.BLOCKED_BY_ENVIRONMENT
                if blocked
                else PipelineState.MODEL_UNAVAILABLE
            )
            return _diagnostic(
                state,
                started,
                failures=(blocker, str(error)),
                notes=(
                    "Real ToothInstanceNet is not configured or unavailable. "
                    "No fixture substitution was performed.",
                ),
                model_name="toothinstancenet",
                segmentation_truth_state=(
                    "blocked_by_environment" if blocked else "not_available"
                ),
                **context,
            )
        except Exception as error:  # noqa: BLE001 - runtime boundary
            return _diagnostic(
                PipelineState.SEGMENTATION_FAILED,
                started,
                failures=(str(error),),
                notes=("Real ToothInstanceNet inference failed. No fixture substitution.",),
                model_name="toothinstancenet",
                segmentation_truth_state="failed",
                **{
                    **context,
                    "limitations": (
                        "Tooth instance counts are not clinical results for a failed run.",
                    ),
                },
            )
        diagnostic = _diagnostic_from_result(result, started, source_kind="uploaded_real_case")
        return CasePipelineDiagnostic(
            **{
                **diagnostic.__dict__,
                **context,
                "fixture": False,
                "segmentation_truth_state": "requires_review",
                "runtime_blocker": None,
                "limitations": (
                    "Model class labels are not verified clinical FDI.",
                ),
                "model_name": result.segmentation.metadata.model_name,
                "model_version": result.segmentation.metadata.model_version,
            }
        )

    try:
        configuration = load_segmentation_configuration()
    except SegmentationConfigurationError as error:
        blocked = assessment.get("capability") == "blocked_by_environment"
        failure = str(error)
        if blocked and assessment.get("blocker"):
            failure = str(assessment["blocker"])
            if "No fixture fallback" not in failure:
                failure = f"{failure} No fixture fallback is used."
        return _diagnostic(
            PipelineState.MODEL_UNAVAILABLE,
            started,
            failures=(failure,),
            notes=("Real segmentation model unavailable. No fixture substitution.",),
            model_name="onnx" if backend != "toothinstancenet" else backend,
            segmentation_truth_state="blocked_by_environment" if blocked else "not_available",
            **context,
        )

    try:
        segmented = OnnxSegmentationEngine(adapter=configuration.adapter()).segment(str(mesh))
    except Exception as error:  # noqa: BLE001
        return _diagnostic(
            PipelineState.SEGMENTATION_FAILED,
            started,
            failures=(str(error),),
            model_name="onnx",
            segmentation_truth_state="failed",
            **{
                **context,
                "limitations": (
                    "Tooth instance counts are not clinical results for a failed run.",
                ),
            },
        )

    segmentation_ms = (perf_counter() - started) * 1000
    identification = ToothIdentificationEngine().identify(segmented, arch)
    scores = [item.confidence.score for item in identification.teeth]
    tooth_instances = tuple(
        {**serialize_identified_tooth(tooth), "arch": arch.value}
        for tooth in identification.teeth
    )
    base = {
        **context,
        "segmentation_truth_state": "requires_review",
        "runtime_blocker": None,
        "limitations": ("ONNX class output is not verified clinical FDI.",),
        "segmentation_runtime_ms": segmentation_ms,
        "tooth_instance_count": len(segmented.instances),
        "identification_confidence": sum(scores) / len(scores) if scores else None,
        "identified_teeth": len(identification.identified),
        "uncertain_teeth": len(identification.uncertain),
        "unidentified_teeth": len(identification.unidentified),
        "tooth_instances": tooth_instances,
        "provenance": identification.provenance.value,
        "experimental": True,
        "fdi_assignments": tuple(
            (tooth.instance.instance_id, tooth.identity.number if tooth.identity else None)
            for tooth in identification.teeth
        ),
        "model_name": segmented.metadata.model_name,
        "model_version": segmented.metadata.model_version,
    }
    if identification.uncertain or identification.unidentified:
        summary = build_anatomical_intelligence_summary(
            identification=identification,
            arch_measurements=None,
        )
        return _diagnostic(
            PipelineState.IDENTIFICATION_INCOMPLETE,
            started,
            **base,
            failures=("Identification is incomplete; planning is blocked.",),
            anatomical_intelligence=summary.payload(),
        )
    try:
        arch_measurements = ArchAnalysisEngine().analyze(identification)
    except ArchAnalysisError as error:
        summary = build_anatomical_intelligence_summary(
            identification=identification,
            arch_measurements=None,
        )
        return _diagnostic(
            PipelineState.IDENTIFICATION_INCOMPLETE,
            started,
            **base,
            failures=(str(error),),
            anatomical_intelligence=summary.payload(),
        )
    summary = build_anatomical_intelligence_summary(
        identification=identification,
        arch_measurements=arch_measurements,
    )
    return _diagnostic(
        PipelineState.PLANNING_READY,
        started,
        **base,
        arch_analysis_available=True,
        arch_measurements=serialize_arch_measurements(arch_measurements),
        anatomical_intelligence=summary.payload(),
        notes=(
            "Segmentation and geometric identification completed for the uploaded mesh. "
            "No fixture substitution.",
        ),
    )
