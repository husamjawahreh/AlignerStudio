"""Case endpoints: create case, upload STL, validate mesh, and plan gating."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from domain.case.models import Case, MeshAsset
from domain.tooth.identification import ArchType
from domain.treatment_plan.input import TreatmentPlanningInput
from engines.geometry.mesh_validation import validate_mesh_file
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import UPLOAD_DIR
from app.engineering_fixture import demo_objectives
from app.pipeline_diagnostics import process_uploaded_case
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


class MovementEditRequest(BaseModel):
    tooth_number: int
    translation_x: float = 0.0
    translation_y: float = 0.0
    translation_z: float = 0.0
    rotation: float = 0.0
    tip: float = 0.0
    torque: float = 0.0
    intrusion: float = 0.0
    extrusion: float = 0.0


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
    return MeshValidationResponse(
        is_valid=result.is_valid,
        triangle_count=result.triangle_count,
        is_watertight=result.is_watertight,
        errors=list(result.errors),
    )


@router.post("/{case_id}/plan", response_model=TreatmentPlanResponse)
def generate_plan(case_id: str) -> TreatmentPlanResponse:
    """Block planning until real segmentation and tooth identification exist."""
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
            reviewed = load_validated_fixture_result(ArchType.UPPER)
        except Exception as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        treatment_input = TreatmentPlanningInput.from_identification(
            reviewed.identification,
            diagnostics=tuple(reviewed.diagnostics.notes)
            if reviewed.status != "planning_ready"
            else (),
        )
        session = treatment_sessions.create_from_treatment_input(
            case_id, treatment_input, demo_objectives()
        )
        if session.proposal.limitations:
            raise HTTPException(status_code=409, detail=list(session.proposal.limitations))
        return TreatmentPlanResponse(
            id=session.proposal.plan_id,
            case_id=case_id,
            stages=[],
            provenance=session.proposal.provenance,
            fixture=session.proposal.fixture,
            notes=(
                "Development fixture treatment proposal created; review stages are "
                "available via treatment session."
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
        return review_bundle(
            treatment_sessions.apply_edit(
                case_id,
                request.tooth_number,
                request.model_dump(exclude={"tooth_number"}),
            )
        )
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
