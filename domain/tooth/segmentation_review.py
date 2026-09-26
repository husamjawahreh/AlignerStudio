"""FV-03 segmentation candidate and review contract.

A candidate is a model partition of an accepted prepared mesh.
It is not FDI, clinical tooth identity, or clinical validation.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from domain.case.preparation import (
    PreparationReadiness,
    failed_job_reference,
    structural_preparation_gate,
)

SEGMENTATION_TRUTH_STATES = frozenset(
    {"SEGMENTED", "PREDICTED", "PROPOSED", "REQUIRES_REVIEW", "VERIFIED", "INVALID"}
)
REVIEW_AUTHORSHIP = frozenset(
    {
        "MODEL_PREDICTION",
        "DOCTOR_MODIFIED",
        "DOCTOR_ACCEPTED",
        "DOCTOR_REJECTED",
        "REQUIRES_REVIEW",
    }
)
SEGMENTATION_INPUT_READINESS = frozenset(
    {
        PreparationReadiness.READY_FOR_SEGMENTATION.value,
        PreparationReadiness.READY_WITH_WARNINGS.value,
    }
)
CAPABILITY_STATES = frozenset(
    {
        "AVAILABLE",
        "DRIVER_UNAVAILABLE",
        "PYTORCH_UNAVAILABLE",
        "CUDA_EXTENSION_UNAVAILABLE",
        "MODEL_CONTRACT_UNAVAILABLE",
        "MODEL_ARTIFACT_UNAVAILABLE",
        "INPUT_UNSUPPORTED",
        "BACKEND_ERROR",
    }
)
ENVIRONMENT_CAPABILITY_STATES = frozenset(
    {
        "DRIVER_UNAVAILABLE",
        "PYTORCH_UNAVAILABLE",
        "CUDA_EXTENSION_UNAVAILABLE",
        "MODEL_ARTIFACT_UNAVAILABLE",
        "BACKEND_ERROR",
    }
)
SEMANTIC_IDENTITY_NOT_ESTABLISHED = "NOT_ESTABLISHED"


class SegmentationReviewError(ValueError):
    """A review edit is not a valid change of the candidate partition."""


def manual_segmentation_contract() -> dict[str, Any]:
    """Manual correction is not a substitute for model segmentation or verification."""
    return {
        "capability": "manual_segmentation_correction",
        "status": "NOT_IMPLEMENTED",
        "substitutes_automatic_segmentation": False,
        "substitutes_model_prediction": False,
        "clinical_verification": False,
        "editor": False,
        "distinct_from": [
            "automatic_model_segmentation",
            "MODEL_PREDICTION",
            "clinical_verification",
        ],
    }


def empty_segmentation() -> dict[str, Any]:
    return {
        "generation": 0,
        "active_run_id": None,
        "runs": [],
        "jobs": [],
        "review": None,
        "semantic_identity": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "fdi_assigned": False,
        "clinically_segmented": False,
        "clinical_accuracy_claim": False,
        "clinical_axes": False,
        "occlusion_established": False,
        "clinical_validation": False,
        "availability": None,
        "capability_state": None,
        "split_available": False,
        "split_unavailable_reason": "SPLIT_UNAVAILABLE",
        "manual_segmentation": manual_segmentation_contract(),
    }


def segmentation_input_reasons(
    artifact: dict[str, Any] | None,
    *,
    geometry: dict[str, Any] | None = None,
) -> list[str]:
    """Structural gate. Mesh finiteness is added by the caller when geometry is loaded."""
    reasons: list[str] = []
    current = artifact or {}
    session = current.get("preparation") if isinstance(current.get("preparation"), dict) else None
    if session is None:
        return ["preparation_missing", "raw_unprepared_input"]
    if session.get("accepted") is not True:
        reasons.append("not_accepted")
    readiness = session.get("readiness")
    if readiness not in SEGMENTATION_INPUT_READINESS:
        reasons.append("readiness_not_segmentation_input")
    operations = list(session.get("operations") or [])
    if not operations:
        reasons.append("raw_unprepared_input")
    active = session.get("active") or {}
    output_path = str(active.get("output_path") or "")
    if output_path.endswith(".partial"):
        reasons.append("partial_output")
    truth = str(active.get("truth_state") or "")
    role = str(active.get("role") or "")
    if truth == "PRESENTATION_ONLY" or role == "PRESENTATION_ONLY":
        reasons.append("presentation_geometry")
    reasons.extend(structural_preparation_gate(session, current.get("sha256")))
    reasons.extend(failed_job_reference(session))
    active_lineage = None
    for item in reversed(session.get("lineage") or []):
        if isinstance(item, dict) and item.get("lifecycle") == "active":
            active_lineage = item
            break
    if operations and active_lineage is None:
        reasons.append("superseded_prepared_artifact")
    elif active_lineage is not None and active_lineage.get("lifecycle") != "active":
        reasons.append("superseded_prepared_artifact")
    if geometry is not None:
        if geometry.get("source_exists") is False:
            reasons.append("source_missing")
        if geometry.get("source_hash_matches") is False:
            reasons.append("source_hash_mismatch")
        if geometry.get("derived_exists") is False:
            reasons.append("derived_missing")
        if geometry.get("derived_hash_matches") is False:
            reasons.append("derived_hash_mismatch")
        if geometry.get("finite") is False:
            reasons.append("geometry_not_finite")
        if geometry.get("face_vertex_consistent") is False:
            reasons.append("face_vertex_inconsistent")
    return list(dict.fromkeys(reasons))


def candidate_instance(
    *,
    instance_id: str,
    run_id: str,
    prepared_sha256: str,
    face_indices: list[int],
    backend_name: str,
    backend_version: str,
    model_id: str,
    model_sha256: str | None,
    raw_model_class: int | None,
    confidence: float | None,
    confidence_available: bool,
    uncertainty: float | None = None,
    uncertainty_available: bool = False,
    truth_state: str = "PREDICTED",
    review_state: str = "MODEL_PREDICTION",
    real_inference: bool = False,
) -> dict[str, Any]:
    if confidence is not None and not confidence_available:
        raise SegmentationReviewError("Confidence was supplied without a model source.")
    if uncertainty is not None and not uncertainty_available:
        raise SegmentationReviewError("Uncertainty was supplied without a model source.")
    if truth_state not in SEGMENTATION_TRUTH_STATES:
        raise SegmentationReviewError("Unknown segmentation truth state.")
    if review_state not in REVIEW_AUTHORSHIP:
        raise SegmentationReviewError("Unknown review authorship.")
    if review_state == "MODEL_PREDICTION" and truth_state == "VERIFIED":
        raise SegmentationReviewError("A model prediction cannot be marked verified.")
    return {
        "instance_id": instance_id,
        "run_id": run_id,
        "geometry_ref": {
            "role": "predicted_partition",
            "prepared_sha256": prepared_sha256,
            "face_indices": list(face_indices),
            "face_count": len(face_indices),
            "replaces_prepared_mesh": False,
        },
        "backend": {
            "name": backend_name,
            "version": backend_version,
            "model_id": model_id,
            "model_sha256": model_sha256,
        },
        "raw_model_class": raw_model_class,
        "model_class_label": "model-defined class",
        "model_class_mapping": SEMANTIC_IDENTITY_NOT_ESTABLISHED,
        "confidence": confidence if confidence_available else None,
        "confidence_available": confidence_available,
        "uncertainty": uncertainty if uncertainty_available else None,
        "uncertainty_available": uncertainty_available,
        "truth_state": truth_state,
        "validation_state": "REQUIRES_REVIEW",
        "review_state": review_state,
        "visible": True,
        "fdi": None,
        "arch_inferred": False,
        "left_right_inferred": False,
        "missing_teeth_inferred": False,
        "real_inference": real_inference,
        "limitations": [
            "Semantic identity is NOT_ESTABLISHED.",
            "The model class is not an FDI number.",
            "Clinical tooth identity, landmarks, roots, and axes are not established.",
        ],
    }


def _faces(instance: dict[str, Any]) -> list[int]:
    return list((instance.get("geometry_ref") or {}).get("face_indices") or [])


def validate_segmentation_run(
    run: dict[str, Any],
    *,
    face_count: int | None,
    finite: bool | None,
) -> dict[str, Any]:
    """Deterministic technical checks. This is not clinical validation."""
    reasons: list[str] = []
    prepared = run.get("prepared_sha256")
    recorded_input = (run.get("input") or {}).get("prepared_sha256")
    if not prepared or prepared != recorded_input:
        reasons.append("input_provenance")
    if not (run.get("source_sha256")):
        reasons.append("source_provenance")
    backend = run.get("backend") or {}
    if not backend.get("name"):
        reasons.append("backend_missing")
    if run.get("real_inference") and not backend.get("model_sha256"):
        reasons.append("model_sha_missing")
    if run.get("fixture") is True:
        reasons.append("fixture_output")
    if run.get("fdi_assigned") is True or run.get("clinical_accuracy_claim") is True:
        reasons.append("clinical_claim")
    if run.get("semantic_identity") != SEMANTIC_IDENTITY_NOT_ESTABLISHED:
        reasons.append("semantic_identity_claimed")
    status = run.get("status")
    instances = list(run.get("instances") or [])
    if status == "blocked" and instances:
        reasons.append("blocked_run_has_instances")
    seen: set[str] = set()
    for instance in instances:
        instance_id = str(instance.get("instance_id") or "")
        if not instance_id or instance_id in seen:
            reasons.append("duplicate_instance_id")
        seen.add(instance_id)
        if instance.get("run_id") != run.get("run_id"):
            reasons.append("lineage_run_mismatch")
        if instance.get("fdi") is not None:
            reasons.append("fdi_present")
        if instance.get("model_class_mapping") != SEMANTIC_IDENTITY_NOT_ESTABLISHED:
            reasons.append("identity_mapping_claimed")
        if instance.get("confidence") is not None and not instance.get("confidence_available"):
            reasons.append("fake_confidence")
        if instance.get("uncertainty") is not None and not instance.get("uncertainty_available"):
            reasons.append("fake_uncertainty")
        if instance.get("truth_state") not in SEGMENTATION_TRUTH_STATES:
            reasons.append("truth_state")
        if instance.get("review_state") not in REVIEW_AUTHORSHIP:
            reasons.append("review_state")
        if (
            instance.get("review_state") == "MODEL_PREDICTION"
            and instance.get("truth_state") == "VERIFIED"
        ):
            reasons.append("auto_verified")
        geometry = instance.get("geometry_ref") or {}
        if geometry.get("prepared_sha256") != prepared:
            reasons.append("orphaned_geometry")
        if geometry.get("replaces_prepared_mesh") is True:
            reasons.append("prepared_mesh_replaced")
        faces = list(geometry.get("face_indices") or [])
        if geometry.get("face_count") != len(faces):
            reasons.append("face_count_inconsistent")
        if face_count is not None and any(index < 0 or index >= face_count for index in faces):
            reasons.append("face_index_out_of_range")
        if not (instance.get("backend") or {}).get("name"):
            reasons.append("instance_backend_missing")
    if finite is False:
        reasons.append("geometry_not_finite")
    unique = list(dict.fromkeys(reasons))
    passed = not unique
    reviewable = passed and status == "completed" and not run.get("blocked")
    report = {
        "passed": passed,
        "reasons": unique,
        "clinical_validation": False,
        "reviewable": reviewable,
    }
    run["technical_validation"] = report
    run["reviewable"] = reviewable
    return report


def _session(artifact: dict[str, Any]) -> dict[str, Any]:
    current = artifact.get("segmentation")
    if not isinstance(current, dict):
        current = empty_segmentation()
        artifact["segmentation"] = current
    return current


def _review(session: dict[str, Any]) -> dict[str, Any]:
    review = session.get("review")
    if not isinstance(review, dict) or not review.get("instances"):
        raise SegmentationReviewError("There is no reviewable segmentation candidate.")
    run_id = review.get("run_id")
    run = next((item for item in session.get("runs") or [] if item.get("run_id") == run_id), None)
    if run is None or not run.get("reviewable"):
        raise SegmentationReviewError("This segmentation run is not reviewable.")
    return review


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _instance_state(instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "instance_id": item.get("instance_id"),
            "review_state": item.get("review_state"),
            "truth_state": item.get("truth_state"),
            "visible": item.get("visible"),
            "faces": list((item.get("geometry_ref") or {}).get("face_indices") or []),
        }
        for item in instances
    ]


def _geometry_state(instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "instance_id": item.get("instance_id"),
            "prepared_sha256": (item.get("geometry_ref") or {}).get("prepared_sha256"),
            "faces": list((item.get("geometry_ref") or {}).get("face_indices") or []),
        }
        for item in instances
    ]


def _prepare(review: dict[str, Any]) -> None:
    instances = list(review.get("instances") or [])
    review["_pending"] = {
        "previous": _canonical_hash(_instance_state(instances)),
        "geometry": _canonical_hash(_geometry_state(instances)),
        "before": copy.deepcopy(instances),
    }


def _operation_id(review: dict[str, Any]) -> str:
    counter = int(review.get("operation_counter") or 0) + 1
    review["operation_counter"] = counter
    return f"op-{counter}"


def _event(
    review: dict[str, Any],
    action: str,
    detail: dict[str, Any],
    *,
    affected: list[str] | None = None,
    restore: bool = False,
) -> dict[str, Any]:
    pending = review.pop("_pending", None) or {}
    instances = list(review.get("instances") or [])
    geometry_now = _canonical_hash(_geometry_state(instances))
    previous_geometry = pending.get("geometry")
    geometry_changed = previous_geometry is not None and geometry_now != previous_geometry
    operation_id = _operation_id(review)
    record = {
        "operation_id": operation_id,
        "operation": action,
        "action": action,
        "parameters": detail,
        "detail": detail,
        "affected_instance_ids": list(affected or []),
        "previous_segmentation_state": pending.get("previous"),
        "resulting_geometry_hash": geometry_now if geometry_changed else None,
        "timestamp": datetime.now(UTC).isoformat(),
        "mutates_model_prediction": False,
    }
    if pending.get("before") is not None and not restore:
        record["before_instances"] = pending["before"]
        review.setdefault("undo", []).append(operation_id)
        if action != "redo":
            review["redo"] = []
    review.setdefault("events", []).append(record)
    review.pop("_pending", None)
    return record


def _geometry_reference_ok(instance: dict[str, Any]) -> bool:
    geometry = instance.get("geometry_ref") or {}
    faces = geometry.get("face_indices")
    if not isinstance(faces, list) or not faces:
        return False
    if geometry.get("face_count") != len(faces):
        return False
    if not geometry.get("prepared_sha256"):
        return False
    if geometry.get("replaces_prepared_mesh") is True:
        return False
    return all(isinstance(index, int) and not isinstance(index, bool) for index in faces)


def _find(review: dict[str, Any], instance_id: str) -> dict[str, Any]:
    match = next(
        (item for item in review.get("instances") or [] if item.get("instance_id") == instance_id),
        None,
    )
    if match is None:
        raise SegmentationReviewError("Segmentation instance was not found.")
    return match


def _next_id(review: dict[str, Any], prefix: str) -> str:
    counter = int(review.get("id_counter") or 0) + 1
    review["id_counter"] = counter
    return f"{prefix}{counter}"


def apply_review_action(
    artifact: dict[str, Any], action: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Apply one doctor review edit. The stored model prediction is not rewritten."""
    session = _session(artifact)
    if action in {"undo", "redo", "reset"}:
        review = session.get("review")
        if not isinstance(review, dict):
            raise SegmentationReviewError("There is no review state to change.")
        if action == "undo":
            stack = list(review.get("undo") or [])
            if not stack:
                raise SegmentationReviewError("There is no review edit to undo.")
            operation_id = stack.pop()
            review["undo"] = stack
            event = next(
                (
                    item
                    for item in review.get("events") or []
                    if item.get("operation_id") == operation_id
                ),
                None,
            )
            if not isinstance(event, dict) or "before_instances" not in event:
                raise SegmentationReviewError("The review operation cannot be restored.")
            review.setdefault("redo", []).append(
                {
                    "operation_id": operation_id,
                    "instances": copy.deepcopy(review.get("instances") or []),
                }
            )
            _prepare(review)
            review["instances"] = copy.deepcopy(event["before_instances"])
            _event(
                review,
                "undo",
                {"restores_operation_id": operation_id},
                affected=list(event.get("affected_instance_ids") or []),
                restore=True,
            )
        elif action == "redo":
            stack = list(review.get("redo") or [])
            if not stack:
                raise SegmentationReviewError("There is no review edit to redo.")
            item = stack.pop()
            review["redo"] = stack
            _prepare(review)
            review["instances"] = copy.deepcopy(item.get("instances") or [])
            _event(
                review,
                "redo",
                {"restores_operation_id": item.get("operation_id")},
                affected=[],
                restore=False,
            )
        else:
            _prepare(review)
            affected = [
                str(item.get("instance_id"))
                for item in review.get("instances") or []
                if item.get("instance_id")
            ]
            review["instances"] = copy.deepcopy(review.get("model_instances") or [])
            _event(review, "reset", {}, affected=affected)
        return session
    review = _review(session)
    if action == "select":
        instance_id = str(payload.get("instance_id") or "")
        _find(review, instance_id)
        review["selected_instance_id"] = instance_id
        _prepare(review)
        _event(review, "select", {"instance_id": instance_id}, affected=[instance_id], restore=True)
        return session
    if action == "inspect":
        instance_id = str(payload.get("instance_id") or "")
        _find(review, instance_id)
        review["inspected_instance_id"] = instance_id
        _prepare(review)
        _event(
            review, "inspect", {"instance_id": instance_id}, affected=[instance_id], restore=True
        )
        return session
    if action in {"hide", "show"}:
        instance = _find(review, str(payload.get("instance_id") or ""))
        _prepare(review)
        instance["visible"] = action == "show"
        _event(
            review,
            action,
            {"instance_id": instance["instance_id"]},
            affected=[instance["instance_id"]],
        )
        return session
    if action == "mark_review":
        instance = _find(review, str(payload.get("instance_id") or ""))
        _prepare(review)
        instance["review_state"] = "REQUIRES_REVIEW"
        instance["validation_state"] = "REQUIRES_REVIEW"
        _event(
            review,
            "mark_review",
            {"instance_id": instance["instance_id"]},
            affected=[instance["instance_id"]],
        )
        return session
    if action == "accept":
        instance = _find(review, str(payload.get("instance_id") or ""))
        _prepare(review)
        instance["review_state"] = "DOCTOR_ACCEPTED"
        if instance.get("truth_state") == "VERIFIED":
            instance["truth_state"] = "PREDICTED"
        _event(
            review,
            "accept",
            {"instance_id": instance["instance_id"]},
            affected=[instance["instance_id"]],
        )
        return session
    if action == "reject":
        instance = _find(review, str(payload.get("instance_id") or ""))
        _prepare(review)
        instance["review_state"] = "DOCTOR_REJECTED"
        instance["truth_state"] = "INVALID"
        _event(
            review,
            "reject",
            {"instance_id": instance["instance_id"]},
            affected=[instance["instance_id"]],
        )
        return session
    if action == "merge":
        left = _find(review, str(payload.get("instance_id") or ""))
        right = _find(review, str(payload.get("other_instance_id") or ""))
        _merge_instances(review, left, right)
        return session
    if action == "split":
        raise SegmentationReviewError(
            "SPLIT_UNAVAILABLE: no safe split control is exposed. No geometry was changed."
        )
    raise SegmentationReviewError("Unknown review action.")


def _merge_instances(review: dict[str, Any], left: dict[str, Any], right: dict[str, Any]) -> None:
    if left["instance_id"] == right["instance_id"]:
        raise SegmentationReviewError("Merge needs two instances.")
    rejected = "DOCTOR_REJECTED"
    if left.get("review_state") == rejected or right.get("review_state") == rejected:
        raise SegmentationReviewError("A rejected instance cannot be merged.")
    left_faces = _faces(left)
    right_faces = _faces(right)
    if set(left_faces) & set(right_faces):
        raise SegmentationReviewError("Merge requires disjoint face sets.")
    if not left_faces or not right_faces:
        raise SegmentationReviewError("Merge requires non-empty instances.")
    left_sha = (left.get("geometry_ref") or {}).get("prepared_sha256")
    right_sha = (right.get("geometry_ref") or {}).get("prepared_sha256")
    if not left_sha or left_sha != right_sha:
        raise SegmentationReviewError("Merge requires the same prepared artifact.")
    if not _geometry_reference_ok(left) or not _geometry_reference_ok(right):
        raise SegmentationReviewError("Merge requires valid geometry references.")
    _prepare(review)
    merged = candidate_instance(
        instance_id=_next_id(review, "inst-m"),
        run_id=left["run_id"],
        prepared_sha256=str(left_sha),
        face_indices=left_faces + [index for index in right_faces if index not in set(left_faces)],
        backend_name=(left.get("backend") or {}).get("name") or "",
        backend_version=(left.get("backend") or {}).get("version") or "",
        model_id=(left.get("backend") or {}).get("model_id") or "",
        model_sha256=(left.get("backend") or {}).get("model_sha256"),
        raw_model_class=None,
        confidence=None,
        confidence_available=False,
        truth_state="PROPOSED",
        review_state="DOCTOR_MODIFIED",
        real_inference=bool(left.get("real_inference")),
    )
    merged["parent_instance_ids"] = [left["instance_id"], right["instance_id"]]
    merged["model_prediction_preserved"] = True
    remaining = [
        item
        for item in review["instances"]
        if item["instance_id"] not in {left["instance_id"], right["instance_id"]}
    ]
    review["instances"] = [*remaining, merged]
    _event(
        review,
        "merge",
        {
            "instance_id": merged["instance_id"],
            "parents": merged["parent_instance_ids"],
            "operation": "merge",
        },
        affected=[left["instance_id"], right["instance_id"], merged["instance_id"]],
    )
