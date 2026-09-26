"""FV-01 segmentation result contract.

Engineering output is not clinical validation. FDI and confidence are included
only when the caller marks them as actually available.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class SegmentationProofError(ValueError):
    """Raised when a segmentation record is not bound to its source mesh."""


class InferenceProofState(StrEnum):
    ENVIRONMENT_READY = "ENVIRONMENT_READY"
    MODEL_MISSING = "MODEL_MISSING"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    GPU_UNAVAILABLE = "GPU_UNAVAILABLE"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    MODEL_CONTRACT_UNKNOWN = "MODEL_CONTRACT_UNKNOWN"
    INFERENCE_READY = "INFERENCE_READY"
    INFERENCE_FAILED = "INFERENCE_FAILED"


class SegmentationOutputClass(StrEnum):
    ENGINEERING_OUTPUT = "ENGINEERING_OUTPUT"
    CLINICALLY_VALIDATED_OUTPUT = "CLINICALLY_VALIDATED_OUTPUT"


def build_review_instance(
    *,
    tooth_ref: str,
    arch: str,
    source_mesh_hash: str | None,
    model_label: int | None,
    confidence: float | None,
    confidence_available: bool,
    fdi: int | None,
    fdi_authoritative: bool,
    vertex_count: int,
    face_count: int,
    centroid: tuple[float, float, float] | None,
) -> dict[str, Any]:
    """One instance a later review phase can read. FDI is omitted unless authoritative."""
    if fdi is not None and not fdi_authoritative:
        raise SegmentationProofError(
            "FDI was supplied without an authoritative numbering method."
        )
    if confidence is not None and not confidence_available:
        raise SegmentationProofError("Confidence was supplied without a model source.")
    return {
        "tooth_ref": tooth_ref,
        "arch": arch,
        "source_mesh_hash": source_mesh_hash,
        "model_label": model_label,
        "confidence": confidence if confidence_available else None,
        "confidence_available": confidence_available,
        "fdi": fdi if fdi_authoritative else None,
        "fdi_authoritative": fdi_authoritative,
        "geometry": {
            "vertex_count": vertex_count,
            "face_count": face_count,
            "centroid": list(centroid) if centroid is not None else None,
        },
    }


def build_segmentation_contract(
    *,
    case_id: str | None,
    job_id: str | None,
    case_input_hash: str | None,
    source_mesh_hash: str | None,
    arch: str | None,
    model_name: str | None,
    model_version: str | None,
    checkpoint_sha256: str | None,
    backend: str | None,
    algorithm_version: str,
    inference_status: str,
    instances: list[dict[str, Any]],
    truth_state: str,
    limitations: tuple[str, ...] | list[str],
    provenance: str,
    created_at: str | None,
    fixture: bool,
    output_class: str = SegmentationOutputClass.ENGINEERING_OUTPUT.value,
    clinical_accuracy_claim: bool = False,
    fdi_authoritative: bool = False,
    timings_ms: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validated = SegmentationOutputClass.CLINICALLY_VALIDATED_OUTPUT.value
    if clinical_accuracy_claim and output_class != validated:
        raise SegmentationProofError(
            "clinical_accuracy_claim requires CLINICALLY_VALIDATED_OUTPUT."
        )
    if output_class == validated and not clinical_accuracy_claim:
        raise SegmentationProofError(
            "CLINICALLY_VALIDATED_OUTPUT requires an explicit clinical accuracy claim."
        )
    if fixture and provenance == "real":
        raise SegmentationProofError("Fixture output cannot use real provenance.")
    return {
        "case_id": case_id,
        "job_id": job_id,
        "input_hash": case_input_hash,
        "case_input_hash": case_input_hash,
        "source_mesh_hash": source_mesh_hash,
        "arch": arch,
        "model_name": model_name,
        "model_version": model_version,
        "checkpoint_sha256": checkpoint_sha256,
        "backend": backend,
        "algorithm_version": algorithm_version,
        "inference_status": inference_status,
        "output_class": output_class,
        "clinical_accuracy_claim": clinical_accuracy_claim,
        "fdi_authoritative": fdi_authoritative,
        "tooth_instances": instances,
        "tooth_instance_count": len(instances),
        "truth_state": truth_state,
        "limitations": list(limitations),
        "provenance": provenance,
        "fixture": fixture,
        "created_at": created_at,
        "timings_ms": timings_ms or {},
    }


def assert_segmentation_bound(
    contract: dict[str, Any],
    *,
    uploaded_mesh_sha256: str,
    case_input_hash: str | None = None,
) -> None:
    """A stored result may be reused only for the mesh that produced it."""
    source = contract.get("source_mesh_hash")
    if source != uploaded_mesh_sha256:
        raise SegmentationProofError(
            "segmentation_result source hash does not match the uploaded STL hash."
        )
    recorded = contract.get("case_input_hash")
    if case_input_hash is not None and recorded not in {None, case_input_hash}:
        raise SegmentationProofError(
            "segmentation_result input_hash does not match the case input hash."
        )
    for instance in contract.get("tooth_instances") or []:
        bound = instance.get("source_mesh_hash")
        if bound not in {None, uploaded_mesh_sha256}:
            raise SegmentationProofError(
                "A tooth instance is bound to a different source mesh."
            )


def refuse_fixture_on_real_record(*, processing_mode: str | None, payload: dict[str, Any]) -> None:
    if processing_mode != "real_case":
        return
    contract = payload.get("segmentation_contract") or {}
    if payload.get("fixture") is True or contract.get("fixture") is True:
        raise SegmentationProofError(
            "Fixture segmentation cannot be persisted as a real-case result."
        )
    payload_mode = payload.get("processing_mode")
    contract_mode = contract.get("processing_mode")
    if payload_mode == "test_fixture" or contract_mode == "test_fixture":
        raise SegmentationProofError(
            "Test-fixture processing cannot be persisted on a real-case record."
        )
