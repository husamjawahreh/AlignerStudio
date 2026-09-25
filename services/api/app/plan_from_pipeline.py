"""Build treatment plans from persisted/real pipeline diagnostics (WP-01).

Never invents FDI. Never loads fixture geometry unless explicitly in TEST_FIXTURE mode.
"""

from __future__ import annotations

from domain.case.provenance import DataProvenance
from domain.tooth.identification import (
    ArchType,
    FDIToothIdentity,
    IdentificationConfidence,
    IdentificationStatus,
    IdentifiedTooth,
    ToothCoordinateSystem,
    ToothIdentificationResult,
    ToothLandmarks,
)
from domain.tooth.segmentation import ToothInstance
from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
from domain.treatment_plan.setup import ToothMovement, TreatmentObjective, TreatmentObjectiveType
from fastapi import HTTPException

from app.pipeline_diagnostics import CasePipelineDiagnostic, PipelineState
from app.segmentation_store import get_segmentation_record
from app.store import case_store
from app.treatment_sessions import treatment_sessions
from app.schemas.cases import TreatmentPlanResponse


def _vector(value) -> tuple[float, float, float] | None:
    if value is None:
        return None
    return (float(value[0]), float(value[1]), float(value[2]))


def _reconstruct_tooth(payload: dict) -> IdentifiedTooth:
    arch = payload.get("arch") or "upper"
    centroid = _vector(payload.get("centroid")) or (0.0, 0.0, 0.0)
    vertices = tuple(tuple(map(float, vertex)) for vertex in payload.get("vertices") or ())
    faces = tuple(tuple(map(int, face)) for face in payload.get("faces") or ())
    instance = ToothInstance(
        instance_id=int(payload["instance_id"]),
        triangle_indices=tuple(range(len(faces))),
        vertex_indices=tuple(range(len(vertices))),
        mesh_vertices=vertices,
        mesh_faces=faces,
        centroid=centroid,
        confidence=float(payload.get("confidence") or 0.0),
        provenance=DataProvenance(payload.get("provenance") or "experimental"),
        fixture=bool(payload.get("fixture")),
        tooth_ref=payload.get("tooth_ref"),
        semantic_label=payload.get("semantic_label"),
        arch=arch,
    )
    # Never invent FDI — only restore when the payload already carries a number.
    identity = None
    fdi_number = payload.get("fdi_number")
    if fdi_number is not None:
        number = int(fdi_number)
        quadrant = number // 10
        position = number % 10
        arch_type = ArchType.UPPER if quadrant in (1, 2) else ArchType.LOWER
        identity = FDIToothIdentity(
            number=number,
            arch=arch_type,
            quadrant=quadrant,
            position_from_midline=position,
        )
    frame_payload = payload.get("coordinate_system") or payload.get("movement_reference_frame")
    if frame_payload:
        semantics = tuple(frame_payload.get("semantics") or ())
        if len(semantics) != 3:
            semantics = (
                "lateral/mesiodistal",
                "anterior/buccolingual",
                "vertical/occlusogingival",
            )
        coordinate_system = ToothCoordinateSystem(
            origin=_vector(frame_payload.get("origin")) or centroid,
            lateral_axis=_vector(frame_payload.get("lateral_axis")) or (1.0, 0.0, 0.0),
            anterior_axis=_vector(frame_payload.get("anterior_axis")) or (0.0, 1.0, 0.0),
            vertical_axis=_vector(frame_payload.get("vertical_axis")) or (0.0, 0.0, 1.0),
            semantics=semantics,  # type: ignore[arg-type]
        )
    else:
        coordinate_system = ToothCoordinateSystem(
            origin=centroid,
            lateral_axis=(1.0, 0.0, 0.0),
            anterior_axis=(0.0, 1.0, 0.0),
            vertical_axis=(0.0, 0.0, 1.0),
        )
    landmarks = None
    landmark_payload = payload.get("landmarks")
    if landmark_payload:
        landmarks = ToothLandmarks(
            centroid=_vector(landmark_payload.get("centroid")) or centroid,
            mesial_point=_vector(landmark_payload.get("mesial_point")) or centroid,
            distal_point=_vector(landmark_payload.get("distal_point")) or centroid,
            occlusal_point=_vector(landmark_payload.get("occlusal_point")) or centroid,
            gingival_point=_vector(landmark_payload.get("gingival_point")) or centroid,
        )
    status_value = payload.get("identification_status") or IdentificationStatus.UNCERTAIN.value
    try:
        status = IdentificationStatus(status_value)
    except ValueError:
        status = IdentificationStatus.UNCERTAIN
    return IdentifiedTooth(
        instance=instance,
        identity=identity,
        landmarks=landmarks,
        coordinate_system=coordinate_system,
        confidence=IdentificationConfidence(
            float(payload.get("confidence") or 0.0),
            status,
            tuple(payload.get("identification_reasons") or ()),
        ),
        provenance=DataProvenance(payload.get("provenance") or "experimental"),
        fixture=bool(payload.get("fixture")),
        tooth_ref=payload.get("tooth_ref"),
        semantic_label=payload.get("semantic_label"),
        planning_mode=payload.get("planning_mode") or "semantic_only_experimental",
    )


def identification_from_arch_diagnostics(
    upper: CasePipelineDiagnostic,
    lower: CasePipelineDiagnostic,
) -> ToothIdentificationResult:
    teeth = tuple(
        _reconstruct_tooth(item)
        for item in list(upper.tooth_instances) + list(lower.tooth_instances)
    )
    fixture = bool(upper.fixture or lower.fixture)
    return ToothIdentificationResult(
        arch=ArchType.UPPER,
        teeth=teeth,
        provenance=DataProvenance.EXPERIMENTAL,
        fixture=fixture,
        notes=(
            f"wp01_pipeline upper={upper.state.value} lower={lower.state.value}; "
            f"mode={upper.processing_mode or lower.processing_mode}"
        ),
    )


def generate_plan_from_arch_diagnostics(
    case_id: str,
    upper: CasePipelineDiagnostic,
    lower: CasePipelineDiagnostic,
    progress_callback=None,
) -> TreatmentPlanResponse:
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    reviewable = {
        PipelineState.IDENTIFICATION_INCOMPLETE.value,
        PipelineState.PLANNING_READY.value,
    }
    if upper.state.value not in reviewable or lower.state.value not in reviewable:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "planning_unavailable",
                "message": "Segmentation did not produce a reviewable identification result.",
                "upper_state": upper.state.value,
                "lower_state": lower.state.value,
                "upper_failures": list(upper.failures),
                "lower_failures": list(lower.failures),
            },
        )
    identification = identification_from_arch_diagnostics(upper, lower)
    # Semantic-only whenever clinical FDI was not produced — never invent numbers.
    has_fdi = any(tooth.identity is not None for tooth in identification.teeth)
    planning_mode = (
        TreatmentPlanningMode.CLINICAL_FDI
        if has_fdi
        else TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL
    )
    treatment_input = TreatmentPlanningInput.from_identification(
        identification,
        diagnostics=tuple(upper.notes) + tuple(lower.notes),
        planning_mode=planning_mode,
    )
    refs = [tooth.tooth_ref for tooth in identification.teeth if tooth.tooth_ref]
    if not refs:
        raise HTTPException(status_code=409, detail="Pipeline result is missing tooth_ref identity")
    objectives = (
        TreatmentObjective(
            "pipeline-review-objective",
            TreatmentObjectiveType.ALIGNMENT,
            "Non-clinical demonstration objective from pipeline geometry; explicit review required.",
            ((refs[0], ToothMovement(translation_x=0.2)),),
            assumptions=(
                "This movement is a deterministic engineering demonstration, "
                "not a clinical recommendation.",
            ),
        ),
    )
    try:
        session = treatment_sessions.create_from_treatment_input(
            case_id, treatment_input, objectives, progress_callback=progress_callback
        )
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "planning_unavailable",
                "message": "Planning could not be completed for the current pipeline data.",
                "reason": str(error),
                "case_id": case_id,
            },
        ) from error
    case.mark_plan_generated()
    case_store.update(case)
    return TreatmentPlanResponse(
        id=session.proposal.plan_id,
        case_id=case_id,
        stages=[],
        provenance=session.proposal.provenance,
        fixture=session.proposal.fixture,
        notes=(
            "Treatment proposal created from uploaded-case pipeline results. "
            "No clinical FDI is asserted unless present in the pipeline output."
        ),
        created_at=case.created_at,
    )


def generate_plan_from_persisted_segmentation(case_id: str, progress_callback=None) -> TreatmentPlanResponse:
    record = get_segmentation_record(case_id)
    if record is None or record.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail="No completed segmentation record is bound to this case. Run analysis first.",
        )
    arches = record.get("arches") or {}
    if "upper" not in arches or "lower" not in arches:
        raise HTTPException(status_code=409, detail="Segmentation record is missing upper/lower arches.")
    upper = _diagnostic_from_payload(arches["upper"])
    lower = _diagnostic_from_payload(arches["lower"])
    return generate_plan_from_arch_diagnostics(case_id, upper, lower, progress_callback)


def _diagnostic_from_payload(payload: dict) -> CasePipelineDiagnostic:
    state = PipelineState(payload.get("state", "identification_incomplete"))
    return CasePipelineDiagnostic(
        state=state,
        source_kind=payload.get("source_kind", "uploaded_real_case"),
        segmentation_runtime_ms=payload.get("segmentation_runtime_ms"),
        total_runtime_ms=float(payload.get("total_runtime_ms") or 0.0),
        tooth_instance_count=int(payload.get("tooth_instance_count") or 0),
        identification_confidence=payload.get("identification_confidence"),
        identified_teeth=int(payload.get("identified_teeth") or 0),
        uncertain_teeth=int(payload.get("uncertain_teeth") or 0),
        unidentified_teeth=int(payload.get("unidentified_teeth") or 0),
        validation_findings=tuple(payload.get("validation_findings") or ()),
        failures=tuple(payload.get("failures") or ()),
        arch_analysis_available=bool(payload.get("arch_analysis_available")),
        notes=tuple(payload.get("notes") or ()),
        provenance=payload.get("provenance", "experimental"),
        fixture=bool(payload.get("fixture")),
        experimental=bool(payload.get("experimental", True)),
        fdi_assignments=tuple(tuple(item) for item in payload.get("fdi_assignments") or ()),
        duplicate_fdi_numbers=tuple(payload.get("duplicate_fdi_numbers") or ()),
        missing_fdi_numbers=tuple(payload.get("missing_fdi_numbers") or ()),
        excluded_fragment_count=int(payload.get("excluded_fragment_count") or 0),
        tooth_instances=tuple(payload.get("tooth_instances") or ()),
        arch_measurements=payload.get("arch_measurements"),
        anatomical_intelligence=payload.get("anatomical_intelligence"),
        processing_mode=payload.get("processing_mode"),
        case_id=payload.get("case_id"),
        job_id=payload.get("job_id"),
        input_hash=payload.get("input_hash"),
        source_mesh_path=payload.get("source_mesh_path"),
        source_mesh_sha256=payload.get("source_mesh_sha256"),
        model_name=payload.get("model_name"),
        model_version=payload.get("model_version"),
    )
