"""API schemas (DTOs) for the /cases endpoints.

These translate between HTTP JSON and domain entities. They intentionally
duplicate a subset of domain fields rather than exposing domain dataclasses
directly over HTTP.
"""

from __future__ import annotations

from datetime import datetime

from domain.case.models import CaseStatus
from domain.case.provenance import DataProvenance
from pydantic import BaseModel


class MeshAssetResponse(BaseModel):
    arch: str
    file_path: str
    original_filename: str
    uploaded_at: datetime


class CaseResponse(BaseModel):
    id: str
    patient_reference: str
    status: CaseStatus
    meshes: list[MeshAssetResponse]
    created_at: datetime
    intake_artifacts: list[dict] = []
    intake_summary: dict = {}


class CreateCaseRequest(BaseModel):
    patient_reference: str = ""


class MeshValidationResponse(BaseModel):
    is_valid: bool
    triangle_count: int
    is_watertight: bool
    errors: list[str]


class ToothPositionResponse(BaseModel):
    fdi_number: int


class StageResponse(BaseModel):
    index: int
    tooth_positions: list[ToothPositionResponse]
    provenance: DataProvenance
    fixture: bool
    notes: str


class TreatmentPlanResponse(BaseModel):
    id: str
    case_id: str
    stages: list[StageResponse]
    provenance: DataProvenance
    fixture: bool
    notes: str
    created_at: datetime
