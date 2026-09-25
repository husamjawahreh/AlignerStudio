"""Case endpoints: create case, upload STL, validate mesh, and plan gating."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from domain.case.models import Case, MeshAsset
from domain.tooth.identification import ArchType, ToothIdentificationResult
from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
from domain.treatment_plan.setup import ToothMovement, TreatmentObjective, TreatmentObjectiveType
from engines.geometry.mesh_validation import validate_mesh_file
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import UPLOAD_DIR
from app.pipeline_diagnostics import process_uploaded_case
from app.processing import live_processing_status, start_processing
from app.schemas.cases import (
    CaseResponse,
    CreateCaseRequest,
    MeshAssetResponse,
    MeshValidationResponse,
    TreatmentPlanResponse,
)
from app.store import case_store
from app.toothinstancenet_configuration import (
    load_validated_fixture_result,
    selected_backend,
)
from app.treatment_sessions import (
    TreatmentSessionError,
    manifest_header,
    review_bundle,
    treatment_sessions,
)

router = APIRouter(prefix="/cases", tags=["cases"])

ALLOWED_ARCHES = {"upper", "lower"}


def _combined_fixture_identification() -> tuple[ToothIdentificationResult, tuple[str, ...]]:
    """Load upper and lower validated fixtures into one semantic-only identification.

    Per-tooth arch/tooth_ref remain authoritative. The container arch field is upper for
    dataclass compatibility only; planning uses tooth.instance.arch / tooth_ref.
    """
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


class ToothResetRequest(BaseModel):
    tooth_number: int | None = None
    tooth_ref: str | None = None


def _to_case_response(case: Case) -> CaseResponse:
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
    if not file.filename or not file.filename.lower().endswith(".stl"):
        raise HTTPException(status_code=400, detail="Only .stl files are accepted")

    dest_path = UPLOAD_DIR / f"{case_id}-{arch}-{uuid4().hex}.stl"
    contents = await file.read()
    dest_path.write_bytes(contents)
    case.add_mesh(MeshAsset(arch=arch, file_path=str(dest_path), original_filename=file.filename))
    case_store.update(case)
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
    case_store.update(case)
    return _to_case_response(case)


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
    """Same behavior as generate_plan, plus optional real-milestone progress reporting."""
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
    if selected_backend() == "toothinstancenet_fixture":
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
                    "message": "Planning could not be completed for the current semantic-only data.",
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
                "Semantic-only experimental treatment proposal created; no clinical FDI "
                "identity is asserted. Review stages are available via treatment session."
            ),
            created_at=case.created_at,
        )
    raise HTTPException(
        status_code=503,
        detail=(
            "Treatment-plan generation is unavailable: real segmentation may be configured, "
            "but tooth identification is a separate Phase 3+ stage and no fake segmentation "
            "fallback is permitted."
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
        return review_bundle(
            treatment_sessions.apply_edit(
                case_id,
                tooth_key,
                request.model_dump(exclude={"tooth_number", "tooth_ref"}),
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
