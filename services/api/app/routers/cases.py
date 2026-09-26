"""Case endpoints: create case, upload STL, validate mesh, and plan gating."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from domain.case.intake import case_arch_summary
from domain.case.models import Case, MeshAsset
from domain.tooth.identification import ArchType, ToothIdentificationResult
from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
from domain.treatment_plan.setup import ToothMovement, TreatmentObjective, TreatmentObjectiveType
from engines.geometry.intake_inspection import derive_cleaned_mesh, inspect_source_file
from engines.geometry.mesh_validation import validate_mesh_file
from engines.geometry.preparation_jobs import PreparationJobConflict
from engines.geometry.scan_preparation import (
    PreparationError,
    accept_preparation,
    apply_operation,
    preview_operation,
    reset_preparation,
    undo_preparation,
)
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import UPLOAD_DIR
from app.pipeline_diagnostics import process_uploaded_case
from app.processing import cancel_processing, live_processing_status, start_processing
from app.schemas.cases import (
    CaseResponse,
    CreateCaseRequest,
    MeshAssetResponse,
    MeshValidationResponse,
    TreatmentPlanResponse,
)
from app.store import case_store
from app.toothinstancenet_configuration import (
    ToothInstanceNetConfigurationError,
    load_validated_fixture_result,
)
from app.treatment_sessions import (
    TreatmentSessionError,
    manifest_header,
    review_bundle,
    treatment_sessions,
)

router = APIRouter(prefix="/cases", tags=["cases"])

ALLOWED_ARCHES = {"upper", "lower"}
ALLOWED_SCAN_SUFFIXES = {".stl", ".ply", ".obj"}


def _combined_fixture_identification() -> tuple[ToothIdentificationResult, tuple[str, ...]]:
    """Load upper and lower validated fixtures into one semantic-only identification.

    TEST_FIXTURE boundary only. Per-tooth arch/tooth_ref remain authoritative.
    """
    from app.processing_modes import ProcessingModeError, resolve_processing_mode

    try:
        resolve_processing_mode()
    except ProcessingModeError as error:
        raise ToothInstanceNetConfigurationError(str(error)) from error
    upper = load_validated_fixture_result(ArchType.UPPER)
    lower = load_validated_fixture_result(ArchType.LOWER)
    diagnostics: list[str] = []
    if upper.status != "planning_ready":
        diagnostics.extend(upper.diagnostics.notes)
    if lower.status != "planning_ready":
        diagnostics.extend(lower.diagnostics.notes)
    combined = replace(
        upper.identification,
        teeth=upper.identification.teeth + lower.identification.teeth,
        notes=(
            f"{upper.identification.notes} | {lower.identification.notes} | "
            "presentation_arches=upper+lower"
        ),
    )
    return combined, tuple(diagnostics)


class MovementEditRequest(BaseModel):
    tooth_number: int | None = None
    tooth_ref: str | None = None
    translation_x: float = 0.0
    translation_y: float = 0.0
    translation_z: float = 0.0
    rotation: float = 0.0
    tip: float = 0.0
    torque: float = 0.0
    angulation: float = 0.0
    intrusion: float = 0.0
    extrusion: float = 0.0
    locked: bool = False
    excluded: bool = False
    # WP-04 provenance — gizmo_edit / numeric_edit / doctor_edit / doctor_reset / system_restore
    reason: str | None = None
    # WP-06: when false, mark staging stale instead of coupled restage
    restage: bool = True


class ToothResetRequest(BaseModel):
    tooth_number: int | None = None
    tooth_ref: str | None = None


class BatchMovementEditRequest(BaseModel):
    """WP-05 multi-tooth target edit — one commit, per-tooth provenance."""

    edits: list[MovementEditRequest]
    reason: str | None = None


class SetupVersionSaveRequest(BaseModel):
    description: str = ""
    author_source: str = "doctor"


class SetupVersionRestoreRequest(BaseModel):
    version_id: str


class SetupVersionCompareRequest(BaseModel):
    left_version_id: str
    right_version_id: str


class StagingRegenerateRequest(BaseModel):
    description: str = ""
    author_source: str = "doctor"


class StagingVersionSaveRequest(BaseModel):
    description: str = ""
    author_source: str = "doctor"


class StagingVersionRestoreRequest(BaseModel):
    staging_version_id: str


class PreparationOperationRequest(BaseModel):
    operation: str
    parameters: dict = {}


class PreparationJobRequest(BaseModel):
    operation: str
    parameters: dict = {}
    mode: str = "apply"


def _to_case_response(case: Case) -> CaseResponse:
    artifacts = list(case.intake_artifacts)
    return CaseResponse(
        id=case.id,
        patient_reference=case.patient_reference,
        status=case.status,
        meshes=[
            MeshAssetResponse(
                arch=mesh.arch,
                file_path=mesh.file_path,
                original_filename=mesh.original_filename,
                uploaded_at=mesh.uploaded_at,
            )
            for mesh in case.meshes
        ],
        created_at=case.created_at,
        intake_artifacts=artifacts,
        intake_summary=case_arch_summary(artifacts),
    )


@router.post("", response_model=CaseResponse)
def create_case(request: CreateCaseRequest) -> CaseResponse:
    case = Case(patient_reference=request.patient_reference)
    case_store.add(case)
    return _to_case_response(case)


@router.get("", response_model=list[CaseResponse])
def list_cases() -> list[CaseResponse]:
    return [_to_case_response(case) for case in case_store.list()]


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: str) -> CaseResponse:
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return _to_case_response(case)


@router.post("/{case_id}/uploads", response_model=CaseResponse)
async def upload_mesh(case_id: str, arch: str, file: UploadFile) -> CaseResponse:
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SCAN_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Only .stl, .ply, and .obj files are accepted",
        )

    dest_path = UPLOAD_DIR / f"{case_id}-{arch}-{uuid4().hex}{suffix}"
    contents = await file.read()
    dest_path.write_bytes(contents)
    case.add_mesh(
        MeshAsset(
            arch=arch,
            file_path=str(dest_path),
            original_filename=file.filename or dest_path.name,
        )
    )
    record = inspect_source_file(
        dest_path,
        case_id=case.id,
        explicit_arch=arch,
        original_filename=file.filename,
    )
    artifacts = [
        item
        for item in case.intake_artifacts
        if item.get("arch", {}).get("arch") != arch
    ]
    artifacts.append(record)
    case.intake_artifacts = artifacts
    case_store.update(case)
    from app.failure_injection import maybe_fail

    maybe_fail("after_upload_persist")
    return _to_case_response(case)


@router.delete("/{case_id}/uploads/{arch}", response_model=CaseResponse)
def remove_mesh(case_id: str, arch: str) -> CaseResponse:
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    mesh = case.remove_mesh(arch)
    if mesh is None:
        raise HTTPException(status_code=404, detail=f"No uploaded mesh for arch '{arch}'")
    Path(mesh.file_path).unlink(missing_ok=True)
    case.intake_artifacts = [
        item for item in case.intake_artifacts if item.get("arch", {}).get("arch") != arch
    ]
    case_store.update(case)
    return _to_case_response(case)


@router.post("/{case_id}/uploads/{arch}/derive-clean")
def derive_clean_mesh(case_id: str, arch: str) -> dict:
    """Write an optional derived cleanup. The stored source file is not replaced."""
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    artifacts = list(case.intake_artifacts)
    source = next((item for item in artifacts if item.get("arch", {}).get("arch") == arch), None)
    if source is None:
        raise HTTPException(status_code=404, detail=f"No intake artifact for arch '{arch}'")
    if source.get("readiness") == "BLOCKED_INVALID_INPUT":
        raise HTTPException(
            status_code=400,
            detail="Invalid source is not repaired in place or replaced.",
        )
    source_path = Path(str(source.get("source_path") or ""))
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail="Source file is missing")
    destination = source_path.with_name(f"{source_path.stem}-derived-{uuid4().hex}.stl")
    derived = derive_cleaned_mesh(source_path, destination)
    source.setdefault("derived_artifacts", []).append(derived)
    source["segmentation_input"] = {
        "role": "SEGMENTATION_INPUT",
        "sha256": source.get("sha256"),
        "source_sha256": source.get("sha256"),
        "derived_sha256": derived["output_sha256"],
        "uses_derived_hash_as_source": False,
    }
    case.intake_artifacts = artifacts
    case_store.update(case)
    return {"source_sha256": source.get("sha256"), "derived": derived}


def _intake_artifact(case: Case, arch: str) -> dict:
    source = next(
        (item for item in case.intake_artifacts if item.get("arch", {}).get("arch") == arch),
        None,
    )
    if source is None:
        raise HTTPException(status_code=404, detail=f"No intake artifact for arch '{arch}'")
    return source


def _prepare(case_id: str, arch: str, action):
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    artifact = _intake_artifact(case, arch)
    try:
        action(artifact)
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    case_store.update(case)
    return _to_case_response(case)


@router.post("/{case_id}/uploads/{arch}/preparation/preview")
def preview_scan_preparation(
    case_id: str, arch: str, request: PreparationOperationRequest
) -> dict:
    """Preview one preparation step. The source file and the case record stay unchanged."""
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    artifact = _intake_artifact(case, arch)
    try:
        return preview_operation(artifact, request.operation, request.parameters)
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{case_id}/uploads/{arch}/preparation/apply", response_model=CaseResponse)
def apply_scan_preparation(
    case_id: str, arch: str, request: PreparationOperationRequest
) -> CaseResponse:
    return _prepare(
        case_id,
        arch,
        lambda artifact: apply_operation(artifact, request.operation, request.parameters),
    )


@router.post("/{case_id}/uploads/{arch}/preparation/undo", response_model=CaseResponse)
def undo_scan_preparation(case_id: str, arch: str) -> CaseResponse:
    return _prepare(case_id, arch, undo_preparation)


@router.post("/{case_id}/uploads/{arch}/preparation/reset", response_model=CaseResponse)
def reset_scan_preparation(case_id: str, arch: str) -> CaseResponse:
    return _prepare(case_id, arch, reset_preparation)


@router.post("/{case_id}/uploads/{arch}/preparation/accept", response_model=CaseResponse)
def accept_scan_preparation(case_id: str, arch: str) -> CaseResponse:
    return _prepare(case_id, arch, accept_preparation)


@router.post("/{case_id}/uploads/{arch}/preparation/jobs")
def submit_preparation_job_route(
    case_id: str, arch: str, request: PreparationJobRequest
) -> dict:
    """Queue orientation, trim, or cleanup. The mesh work does not run on this thread."""
    from app.preparation_jobs import submit_case_preparation_job

    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    try:
        return submit_case_preparation_job(
            case, arch, request.operation, request.parameters, request.mode
        )
    except PreparationJobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{case_id}/uploads/{arch}/preparation/jobs/{job_id}")
def get_preparation_job_route(case_id: str, arch: str, job_id: str) -> dict:
    from app.preparation_jobs import preparation_job_for_case

    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    try:
        job = preparation_job_for_case(case, arch, job_id)
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Preparation job not found")
    return job


@router.post("/{case_id}/uploads/{arch}/preparation/jobs/{job_id}/cancel")
def cancel_preparation_job_route(case_id: str, arch: str, job_id: str) -> dict:
    from app.preparation_jobs import cancel_case_preparation_job

    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    try:
        job = cancel_case_preparation_job(case, arch, job_id)
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Preparation job not found")
    return job


class SegmentationReviewRequest(BaseModel):
    action: str
    instance_id: str | None = None
    other_instance_id: str | None = None
    face_indices: list[int] = []


@router.post("/{case_id}/uploads/{arch}/segmentation/jobs")
def submit_segmentation_job_route(case_id: str, arch: str) -> dict:
    """Queue segmentation of an accepted prepared artifact. Inference stays off this thread."""
    from app.segmentation_jobs import (
        SegmentationInputError,
        SegmentationJobConflict,
        submit_case_segmentation_job,
    )

    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    try:
        return submit_case_segmentation_job(case, arch)
    except SegmentationJobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SegmentationInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{case_id}/uploads/{arch}/segmentation/jobs/{job_id}")
def get_segmentation_job_route(case_id: str, arch: str, job_id: str) -> dict:
    from engines.geometry.scan_preparation import PreparationError

    from app.segmentation_jobs import segmentation_job_for_case

    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    try:
        job = segmentation_job_for_case(case, arch, job_id)
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Segmentation job not found")
    return job


@router.post("/{case_id}/uploads/{arch}/segmentation/jobs/{job_id}/cancel")
def cancel_segmentation_job_route(case_id: str, arch: str, job_id: str) -> dict:
    from engines.geometry.scan_preparation import PreparationError

    from app.segmentation_jobs import cancel_case_segmentation_job

    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    try:
        job = cancel_case_segmentation_job(case, arch, job_id)
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Segmentation job not found")
    return job


@router.post("/{case_id}/uploads/{arch}/segmentation/review", response_model=CaseResponse)
def review_segmentation_route(
    case_id: str, arch: str, request: SegmentationReviewRequest
) -> CaseResponse:
    from domain.tooth.segmentation_review import SegmentationReviewError

    from app.segmentation_jobs import review_case_segmentation

    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    try:
        updated = review_case_segmentation(
            case,
            arch,
            request.action,
            {
                "instance_id": request.instance_id,
                "other_instance_id": request.other_instance_id,
                "face_indices": request.face_indices,
            },
        )
    except SegmentationReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_case_response(updated)


@router.post("/{case_id}/uploads/{arch}/segmentation/external-evidence")
def import_external_segmentation_evidence_route(case_id: str, arch: str, payload: dict) -> dict:
    """Import external CUDA evidence. Verification is computed here, not taken from the client."""
    from engines.geometry.scan_preparation import PreparationError

    from app.segmentation_jobs import import_case_external_segmentation_evidence

    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    try:
        return import_case_external_segmentation_evidence(case, arch, payload)
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{case_id}/uploads/{arch}/validate", response_model=MeshValidationResponse)
def validate_case_mesh(case_id: str, arch: str) -> MeshValidationResponse:
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    mesh = next((asset for asset in case.meshes if asset.arch == arch), None)
    if mesh is None:
        raise HTTPException(status_code=404, detail=f"No uploaded mesh for arch '{arch}'")

    result = validate_mesh_file(mesh.file_path)
    if result.is_valid:
        case.mark_validated()
    else:
        case.mark_rejected()
    case_store.update(case)
    return MeshValidationResponse(
        is_valid=result.is_valid,
        triangle_count=result.triangle_count,
        is_watertight=result.is_watertight,
        errors=list(result.errors),
    )


@router.post("/{case_id}/plan", response_model=TreatmentPlanResponse)
def generate_plan(case_id: str) -> TreatmentPlanResponse:
    """Block planning until real segmentation and tooth identification exist."""
    return generate_plan_with_progress(case_id)


def generate_plan_with_progress(
    case_id: str, progress_callback: Callable[[int, str], None] | None = None
) -> TreatmentPlanResponse:
    """Same behavior as generate_plan, plus optional real-milestone progress reporting.

    WP-01: prefer persisted uploaded-case pipeline results. Fixture-backed planning
    remains available only behind the explicit TEST_FIXTURE allow flag.
    """
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    present_arches = {mesh.arch for mesh in case.meshes}
    missing_arches = sorted(ALLOWED_ARCHES - present_arches)
    if missing_arches:
        raise HTTPException(
            status_code=400,
            detail=(
                "Both upper and lower STL files are required; "
                f"missing: {', '.join(missing_arches)}."
            ),
        )

    from app.plan_from_pipeline import generate_plan_from_persisted_segmentation
    from app.processing_modes import ProcessingMode, ProcessingModeError, resolve_processing_mode
    from app.segmentation_store import get_segmentation_record

    record = get_segmentation_record(case_id)
    if record and record.get("status") == "completed":
        return generate_plan_from_persisted_segmentation(case_id, progress_callback)

    try:
        mode = resolve_processing_mode()
    except ProcessingModeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    if mode is ProcessingMode.TEST_FIXTURE:
        # Explicit test/regression path only — still requires hash-bound fixture loads
        # when source meshes are provided to the fixture loader.
        try:
            identification, fixture_diagnostics = _combined_fixture_identification()
        except Exception as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        treatment_input = TreatmentPlanningInput.from_identification(
            identification,
            diagnostics=fixture_diagnostics,
            planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL,
        )
        refs = [tooth.tooth_ref for tooth in identification.teeth]
        if not refs or any(ref is None for ref in refs):
            raise HTTPException(
                status_code=409, detail="Semantic-only artifact is missing tooth_ref"
            )
        upper_count = sum(1 for tooth in identification.teeth if tooth.instance.arch == "upper")
        lower_count = sum(1 for tooth in identification.teeth if tooth.instance.arch == "lower")
        if upper_count != 14 or lower_count != 14:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Validated real-case fixture must provide 14 upper and 14 lower "
                    f"semantic tooth instances; got upper={upper_count}, lower={lower_count}."
                ),
            )
        objectives = (
            TreatmentObjective(
                "semantic-only-experimental-review",
                TreatmentObjectiveType.ALIGNMENT,
                "Non-clinical experimental demonstration objective; explicit review required.",
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
                    "message": (
                        "Planning could not be completed for the current semantic-only data."
                    ),
                    "reason": str(error),
                    "case_id": case_id,
                },
            ) from error
        if session.proposal.limitations:
            raise HTTPException(status_code=409, detail=list(session.proposal.limitations))
        return TreatmentPlanResponse(
            id=session.proposal.plan_id,
            case_id=case_id,
            stages=[],
            provenance=session.proposal.provenance,
            fixture=session.proposal.fixture,
            notes=(
                "TEST_FIXTURE semantic-only treatment proposal. Not a silent substitute for "
                "uploaded-case ToothInstanceNet processing."
            ),
            created_at=case.created_at,
        )

    raise HTTPException(
        status_code=503,
        detail=(
            "Treatment-plan generation requires completed real-case segmentation bound to this "
            "case. Run analysis on the uploaded STLs first. Fixture substitution is not used."
        ),
    )


@router.post("/{case_id}/pipeline/{arch}")
def process_case_pipeline(case_id: str, arch: str) -> dict:
    """Run the configured real model pipeline and return engineering diagnostics."""
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if arch not in ALLOWED_ARCHES:
        raise HTTPException(status_code=400, detail=f"arch must be one of {sorted(ALLOWED_ARCHES)}")
    mesh = next((asset for asset in case.meshes if asset.arch == arch), None)
    if mesh is None:
        raise HTTPException(status_code=404, detail=f"No uploaded mesh for arch '{arch}'")
    return process_uploaded_case(mesh.file_path, ArchType(arch)).payload()


@router.post("/{case_id}/processing")
def begin_processing(case_id: str) -> dict:
    try:
        return start_processing(case_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{case_id}/processing/cancel")
def cancel_case_processing(case_id: str) -> dict:
    case = case_store.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        return cancel_processing(case_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{case_id}/processing-status")
def get_processing_status(case_id: str) -> dict:
    if case_store.get(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    status = live_processing_status(case_id)
    if status is None:
        raise HTTPException(status_code=404, detail="No processing job exists for this case")
    return status


@router.post("/demo")
def create_engineering_demo() -> dict:
    """Create a visibly fixture-labeled complete pipeline demo."""
    case = Case(patient_reference="engineering-fixture-demo")
    case.mark_plan_generated()
    case_store.add(case)
    return {
        "case": _to_case_response(case),
        "review_bundle": review_bundle(treatment_sessions.create_engineering_fixture(case.id)),
    }


@router.get("/{case_id}/treatment")
def get_treatment(case_id: str) -> dict:
    try:
        return review_bundle(treatment_sessions.get(case_id))
    except TreatmentSessionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{case_id}/treatment/edits")
def apply_treatment_edit(case_id: str, request: MovementEditRequest) -> dict:
    try:
        tooth_key = request.tooth_ref if request.tooth_ref is not None else request.tooth_number
        if tooth_key is None:
            raise ValueError("Either tooth_number or tooth_ref is required")
        payload = request.model_dump(exclude={"tooth_number", "tooth_ref", "reason", "restage"})
        return review_bundle(
            treatment_sessions.apply_edit(
                case_id,
                tooth_key,
                payload,
                reason=request.reason,
                restage=request.restage,
            )
        )
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{case_id}/treatment/reset")
def reset_treatment_tooth(case_id: str, request: ToothResetRequest) -> dict:
    try:
        tooth_key = request.tooth_ref if request.tooth_ref is not None else request.tooth_number
        if tooth_key is None:
            raise ValueError("Either tooth_number or tooth_ref is required")
        return review_bundle(treatment_sessions.reset_tooth(case_id, tooth_key))
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{case_id}/treatment/reset-all")
def reset_all_treatment_edits(case_id: str) -> dict:
    try:
        return review_bundle(treatment_sessions.reset_all(case_id))
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{case_id}/treatment/recalculate")
def recalculate_treatment(case_id: str) -> dict:
    try:
        return review_bundle(treatment_sessions.recalculate(case_id))
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{case_id}/treatment/edits/batch")
def apply_treatment_edits_batch(case_id: str, request: BatchMovementEditRequest) -> dict:
    """WP-05 multi-tooth target edit with a single restage/validate pass."""
    try:
        edits: list[tuple[int | str, dict]] = []
        for item in request.edits:
            tooth_key = item.tooth_ref if item.tooth_ref is not None else item.tooth_number
            if tooth_key is None:
                raise ValueError("Each edit requires tooth_number or tooth_ref")
            payload = item.model_dump(exclude={"tooth_number", "tooth_ref", "reason"})
            edits.append((tooth_key, payload))
        return review_bundle(
            treatment_sessions.apply_edits(case_id, edits, reason=request.reason)
        )
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{case_id}/treatment/versions")
def list_treatment_versions(case_id: str) -> dict:
    try:
        return {"versions": treatment_sessions.list_versions(case_id)}
    except TreatmentSessionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{case_id}/treatment/versions")
def save_treatment_version(case_id: str, request: SetupVersionSaveRequest) -> dict:
    try:
        return review_bundle(
            treatment_sessions.save_version(
                case_id,
                description=request.description,
                author_source=request.author_source or "doctor",
            )
        )
    except TreatmentSessionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{case_id}/treatment/versions/restore")
def restore_treatment_version(case_id: str, request: SetupVersionRestoreRequest) -> dict:
    try:
        return review_bundle(
            treatment_sessions.restore_version(case_id, request.version_id)
        )
    except TreatmentSessionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{case_id}/treatment/versions/compare")
def compare_treatment_versions(case_id: str, request: SetupVersionCompareRequest) -> dict:
    try:
        return treatment_sessions.compare_versions(
            case_id, request.left_version_id, request.right_version_id
        )
    except TreatmentSessionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{case_id}/treatment/staging/regenerate")
def regenerate_treatment_staging(case_id: str, request: StagingRegenerateRequest) -> dict:
    """WP-06 explicit staging regenerate — does not silently rebase a stale plan."""
    try:
        return review_bundle(
            treatment_sessions.regenerate_staging(
                case_id,
                description=request.description,
                author_source=request.author_source or "doctor",
            )
        )
    except TreatmentSessionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{case_id}/treatment/staging/versions")
def list_staging_versions(case_id: str) -> dict:
    try:
        return {"versions": treatment_sessions.list_staging_versions(case_id)}
    except TreatmentSessionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{case_id}/treatment/staging/versions")
def save_staging_version(case_id: str, request: StagingVersionSaveRequest) -> dict:
    try:
        return review_bundle(
            treatment_sessions.save_staging_version(
                case_id,
                description=request.description,
                author_source=request.author_source or "doctor",
            )
        )
    except TreatmentSessionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{case_id}/treatment/staging/versions/restore")
def restore_staging_version(case_id: str, request: StagingVersionRestoreRequest) -> dict:
    try:
        return review_bundle(
            treatment_sessions.restore_staging_version(case_id, request.staging_version_id)
        )
    except TreatmentSessionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{case_id}/treatment/proposals")
def get_treatment_proposals(case_id: str) -> dict:
    try:
        bundle = review_bundle(treatment_sessions.get(case_id))
        return {"iprSites": bundle["iprSites"], "attachmentSites": bundle["attachmentSites"]}
    except TreatmentSessionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


class IPRStatusRequest(BaseModel):
    status: str


class IPRAmountRequest(BaseModel):
    amount: float


class AttachmentStatusRequest(BaseModel):
    status: str


@router.patch("/{case_id}/treatment/proposals/ipr/{site_id}/status")
def patch_ipr_status(case_id: str, site_id: str, body: IPRStatusRequest) -> dict:
    try:
        return review_bundle(treatment_sessions.set_ipr_status(case_id, site_id, body.status))
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.patch("/{case_id}/treatment/proposals/ipr/{site_id}/amount")
def patch_ipr_amount(case_id: str, site_id: str, body: IPRAmountRequest) -> dict:
    try:
        return review_bundle(treatment_sessions.modify_ipr_amount(case_id, site_id, body.amount))
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.patch("/{case_id}/treatment/proposals/attachments/{site_id}/status")
def patch_attachment_status(case_id: str, site_id: str, body: AttachmentStatusRequest) -> dict:
    try:
        return review_bundle(
            treatment_sessions.set_attachment_status(case_id, site_id, body.status)
        )
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{case_id}/treatment/proposals/reset")
def reset_treatment_proposals(case_id: str) -> dict:
    try:
        return review_bundle(treatment_sessions.reset_proposals(case_id))
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


class SetupAlternativeRequest(BaseModel):
    alternative_id: str


class ProductionSourceSelectRequest(BaseModel):
    stage_index: int | None = None
    source_kind: str = "selected_stage"


@router.post("/{case_id}/treatment/setup-alternatives/select")
def select_setup_alternative(case_id: str, body: SetupAlternativeRequest) -> dict:
    """Doctor accepts a validated assisted setup alternative."""
    try:
        return review_bundle(
            treatment_sessions.select_setup_alternative(case_id, body.alternative_id)
        )
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{case_id}/treatment/planning-intelligence")
def get_planning_intelligence(case_id: str) -> dict:
    try:
        session = treatment_sessions.ensure_planning_intelligence(case_id)
        bundle = review_bundle(session)
        payload = bundle.get("planningIntelligence")
        if payload is None:
            raise TreatmentSessionError("Planning intelligence unavailable for this case")
        return payload
    except TreatmentSessionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{case_id}/dental-intelligence")
def get_dental_intelligence(case_id: str) -> dict:
    """Dental Intelligence 2.0 — truth-preserving clinical intelligence document (WP-02)."""
    if case_store.get(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    from app.intelligence_store import (
        build_and_store_dental_intelligence,
        get_dental_intelligence_record,
    )

    record = get_dental_intelligence_record(case_id)
    if record is not None:
        return record
    try:
        return build_and_store_dental_intelligence(case_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{case_id}/dental-intelligence/rebuild")
def rebuild_dental_intelligence(case_id: str) -> dict:
    """Rebuild Dental Intelligence 2.0 from the persisted completed segmentation record."""
    if case_store.get(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    from app.intelligence_store import build_and_store_dental_intelligence

    try:
        return build_and_store_dental_intelligence(case_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{case_id}/export")
def export_treatment(case_id: str) -> FileResponse:
    try:
        package = treatment_sessions.export(case_id, Path(UPLOAD_DIR) / f"{case_id}-export")
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return FileResponse(
        package.zip_path,
        media_type="application/zip",
        filename=f"alignerstudio-{case_id}-export.zip",
        headers={"X-AlignerStudio-Manifest": manifest_header(package)},
    )


@router.post("/{case_id}/production/source")
def select_production_source(case_id: str, body: ProductionSourceSelectRequest) -> dict:
    """WP-10: explicitly select the production source stage/target (never silent)."""
    try:
        session = treatment_sessions.select_production_source(
            case_id,
            stage_index=body.stage_index,
            source_kind=body.source_kind,
        )
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return review_bundle(session)


@router.post("/{case_id}/production/source/clear")
def clear_production_source(case_id: str) -> dict:
    """WP-10: clear production source selection."""
    try:
        session = treatment_sessions.clear_production_source(case_id)
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return review_bundle(session)


@router.post("/{case_id}/export/verify")
def verify_treatment_export(case_id: str) -> dict:
    """Export then re-open the package and verify manifest/file hashes."""
    try:
        return treatment_sessions.verify_export(
            case_id, Path(UPLOAD_DIR) / f"{case_id}-export-verify"
        )
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{case_id}/export/reopen")
def reopen_treatment_export(case_id: str) -> dict:
    """Export then reopen for audit. Does not restore an editable treatment session."""
    try:
        return treatment_sessions.reopen_export_for_audit(
            case_id, Path(UPLOAD_DIR) / f"{case_id}-export-reopen"
        )
    except (TreatmentSessionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
