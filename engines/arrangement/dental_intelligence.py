"""Dental Intelligence 2.0 builder — consumes genuine processed case data (WP-02).

Never invents FDI, clinical dental axes, landmarks, or occlusion.
Distinguishes mesh PCA principal directions from clinical dental axes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from domain.case.provenance import DataProvenance
from domain.tooth.intelligence_v2 import (
    INTELLIGENCE_CONTRACT_VERSION,
    ArchIntelligence,
    CapabilityReadiness,
    CaseDentalIntelligence,
    IntelligenceTruthState,
    ToothIntelligence,
    TruthValue,
    computed,
    not_available,
    requires_review,
)
from engines.arrangement.geometry_metrics import (
    ALGORITHM_ID,
    ALGORITHM_VERSION,
    GeometryMetricsError,
    compute_geometry_metrics,
)
from engines.occlusion.capability_engine import (
    build_advanced_anatomy_report,
    build_occlusion_result,
    intelligence_truth_for_occlusion,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _provenance(value: str | None) -> DataProvenance:
    try:
        return DataProvenance(value or "experimental")
    except ValueError:
        return DataProvenance.EXPERIMENTAL


def build_case_dental_intelligence(
    *,
    case_id: str,
    segmentation_record: dict[str, Any],
) -> CaseDentalIntelligence:
    """Build a versioned intelligence document from WP-01 persisted segmentation results."""
    started = perf_counter()
    if not segmentation_record or segmentation_record.get("status") != "completed":
        raise ValueError("Completed segmentation record is required for Dental Intelligence 2.0")
    if segmentation_record.get("processing_mode") == "test_fixture" and segmentation_record.get(
        "fixture", True
    ):
        # Fixture records may still be inspected in tests, but are marked fixture=True.
        pass

    arches_payload = segmentation_record.get("arches") or {}
    teeth: list[ToothIntelligence] = []
    arch_summaries: list[ArchIntelligence] = []
    quality_findings: list[str] = []
    per_tooth_ms: list[float] = []

    for arch_name in ("upper", "lower"):
        arch_data = arches_payload.get(arch_name)
        if not isinstance(arch_data, dict):
            quality_findings.append(f"Missing arch segmentation payload: {arch_name}.")
            continue
        arch_teeth, arch_summary, arch_findings, timings = _build_arch(
            arch_name=arch_name,
            arch_payload=arch_data,
            model_name=segmentation_record.get("model_name") or arch_data.get("model_name"),
            model_version=segmentation_record.get("model_version") or arch_data.get("model_version"),
        )
        teeth.extend(arch_teeth)
        arch_summaries.append(arch_summary)
        quality_findings.extend(arch_findings)
        per_tooth_ms.extend(timings)

    fixture = bool(segmentation_record.get("processing_mode") == "test_fixture") or any(
        tooth.fixture for tooth in teeth
    )
    provenance = DataProvenance.FIXTURE if fixture else DataProvenance.EXPERIMENTAL
    generated_at = _now()

    occlusion_result = build_occlusion_result(
        case_id=case_id,
        segmentation_record=segmentation_record,
        generated_at=generated_at,
    )
    advanced_anatomy = build_advanced_anatomy_report(
        case_id=case_id,
        segmentation_record=segmentation_record,
        tooth_intelligence_summaries=[tooth.payload() for tooth in teeth],
        generated_at=generated_at,
    )
    occlusion_truth = intelligence_truth_for_occlusion(occlusion_result.capability_state)
    occlusion_payload = {
        **occlusion_result.representation.payload(),
        "capability_state": occlusion_result.capability_state.value,
        "contract_version": occlusion_result.contract_version,
        "registration": occlusion_result.registration.payload(),
        "contact_candidates": [c.payload() for c in occlusion_result.contact_candidates],
        "arch_relationship": occlusion_result.arch_relationship.payload(),
        "readiness": occlusion_result.readiness.payload(),
        "freshness": occlusion_result.freshness.value,
        "advanced_anatomy": advanced_anatomy.payload(),
        "clinically_approved": False,
        "occlusion_validated": False,
        "limitations": list(occlusion_result.limitations),
        "timings_ms": dict(occlusion_result.timings_ms),
    }
    occlusion = TruthValue(
        state=occlusion_truth,
        value=occlusion_payload,
        reason="; ".join(occlusion_result.limitations[:2])
        if occlusion_result.limitations
        else None,
        algorithm=occlusion_result.algorithm or "occlusion_gate",
        algorithm_version=occlusion_result.algorithm_version,
    )

    readiness = _capability_readiness(
        teeth,
        arch_summaries,
        quality_findings,
        occlusion_state=occlusion_truth,
    )
    overall = _overall_state(teeth, readiness)

    limitations = (
        "Clinical FDI is never invented; unresolved identity remains Not Available.",
        "Mesh principal directions are geometric PCA, not clinical dental axes.",
        "Landmarks remain Not Available unless supplied by an upstream geometric/clinical method.",
        "Occlusion remains Not Available without bite/registration evidence.",
        "Root/bone anatomy is Not Available for crown-only STL inputs.",
        "COMPUTED geometry metrics are not clinical validation.",
        "Geometric contact candidates are never clinical occlusal diagnoses.",
    )

    total_ms = (perf_counter() - started) * 1000
    return CaseDentalIntelligence(
        contract_version=INTELLIGENCE_CONTRACT_VERSION,
        case_id=case_id,
        job_id=segmentation_record.get("job_id"),
        input_hash=segmentation_record.get("input_hash"),
        processing_mode=segmentation_record.get("processing_mode"),
        generated_at=generated_at,
        teeth=tuple(teeth),
        arches=tuple(arch_summaries),
        occlusion=occlusion,
        data_quality_findings=tuple(dict.fromkeys(quality_findings)),
        capability_readiness=readiness,
        overall_truth_state=overall,
        provenance=provenance,
        fixture=fixture,
        model_name=segmentation_record.get("model_name"),
        model_version=segmentation_record.get("model_version"),
        timings_ms={
            "total": total_ms,
            "per_tooth_mean": (sum(per_tooth_ms) / len(per_tooth_ms)) if per_tooth_ms else None,
            "per_tooth_max": max(per_tooth_ms) if per_tooth_ms else None,
            "tooth_count_timed": float(len(per_tooth_ms)),
            "occlusion_ms": occlusion_result.timings_ms.get("total_ms"),
            "anatomy_capability_ms": advanced_anatomy.timings_ms.get("anatomy_capability_ms"),
        },
        limitations=limitations,
    )


def _build_arch(
    *,
    arch_name: str,
    arch_payload: dict[str, Any],
    model_name: str | None,
    model_version: str | None,
) -> tuple[list[ToothIntelligence], ArchIntelligence, list[str], list[float]]:
    findings: list[str] = []
    teeth_out: list[ToothIntelligence] = []
    timings: list[float] = []
    instances = list(arch_payload.get("tooth_instances") or [])
    source_mesh_path = arch_payload.get("source_mesh_path")
    source_mesh_sha256 = arch_payload.get("source_mesh_sha256")
    fixture = bool(arch_payload.get("fixture"))
    provenance = _provenance(arch_payload.get("provenance"))

    if not instances:
        findings.append(f"{arch_name}: no tooth instances in segmentation payload.")

    for item in instances:
        tooth_started = perf_counter()
        tooth = _build_tooth(
            item=item,
            arch_fallback=arch_name,
            source_mesh_path=source_mesh_path,
            source_mesh_sha256=source_mesh_sha256,
            model_name=model_name,
            model_version=model_version,
            fixture_default=fixture,
            provenance_default=provenance,
        )
        teeth_out.append(tooth)
        timings.append((perf_counter() - tooth_started) * 1000)
        findings.extend(tooth.quality_findings)

    resolved_fdi = sum(
        1
        for tooth in teeth_out
        if tooth.fdi_number.value is not None
        and tooth.fdi_number.state
        in (IntelligenceTruthState.VERIFIED, IntelligenceTruthState.REQUIRES_REVIEW)
    )
    unresolved = sum(
        1 for tooth in teeth_out if tooth.fdi_number.state is IntelligenceTruthState.NOT_AVAILABLE
    )
    geometry_ready = sum(
        1 for tooth in teeth_out if tooth.geometry.state is IntelligenceTruthState.COMPUTED
    )
    landmarks_count = sum(
        1
        for tooth in teeth_out
        if tooth.landmarks.state
        in (IntelligenceTruthState.VERIFIED, IntelligenceTruthState.COMPUTED)
    )
    clinical_axes = sum(
        1
        for tooth in teeth_out
        if tooth.clinical_dental_axes.state
        in (IntelligenceTruthState.VERIFIED, IntelligenceTruthState.COMPUTED)
    )

    if unresolved == len(teeth_out) and teeth_out:
        arch_state = IntelligenceTruthState.REQUIRES_REVIEW
    elif geometry_ready == 0 and teeth_out:
        arch_state = IntelligenceTruthState.NOT_AVAILABLE
    elif unresolved > 0:
        arch_state = IntelligenceTruthState.REQUIRES_REVIEW
    else:
        arch_state = IntelligenceTruthState.COMPUTED

    summary = ArchIntelligence(
        arch=arch_name,
        tooth_instance_count=len(teeth_out),
        resolved_fdi_count=resolved_fdi,
        unresolved_identity_count=unresolved,
        geometry_ready_count=geometry_ready,
        landmarks_available_count=landmarks_count,
        clinical_axes_available_count=clinical_axes,
        quality_findings=tuple(dict.fromkeys(findings)),
        overall_truth_state=arch_state,
        provenance=provenance,
        fixture=fixture,
        source_mesh_path=source_mesh_path,
        source_mesh_sha256=source_mesh_sha256,
    )
    return teeth_out, summary, findings, timings


def _build_tooth(
    *,
    item: dict[str, Any],
    arch_fallback: str,
    source_mesh_path: str | None,
    source_mesh_sha256: str | None,
    model_name: str | None,
    model_version: str | None,
    fixture_default: bool,
    provenance_default: DataProvenance,
) -> ToothIntelligence:
    quality: list[str] = []
    instance_id = int(item.get("instance_id", -1))
    tooth_ref = item.get("tooth_ref")
    arch = item.get("arch") or arch_fallback
    if not tooth_ref:
        tooth_ref = f"{arch}:instance:{instance_id}" if instance_id >= 0 else None
        quality.append(f"instance {instance_id}: tooth_ref was missing; derived stable ref for tracking only.")

    fixture = bool(item.get("fixture", fixture_default))
    provenance = _provenance(item.get("provenance") or provenance_default.value)

    # FDI — never invent. Model-supplied numbers require review; geometric verified would be VERIFIED.
    fdi_raw = item.get("fdi_number")
    if fdi_raw is None:
        fdi_truth = not_available("Clinical tooth numbering has not been resolved for this tooth.")
    else:
        fdi_truth = requires_review(
            int(fdi_raw),
            reason=(
                "FDI number present from upstream model/mapping; not clinically verified. "
                "Requires doctor review."
            ),
            algorithm="upstream_identity",
        )

    semantic_raw = item.get("semantic_label")
    if semantic_raw is None:
        semantic_truth = not_available("No semantic class label supplied by segmentation.")
    else:
        semantic_truth = requires_review(
            int(semantic_raw),
            reason="Seven-class / semantic label is experimental and not clinical FDI.",
            algorithm="upstream_semantic_label",
        )

    # Confidence: preserve null/unknown rather than inventing.
    confidence = item.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None
            quality.append(f"instance {instance_id}: non-numeric confidence discarded.")

    vertices = item.get("vertices") or []
    faces = item.get("faces") or []
    try:
        metrics = compute_geometry_metrics(vertices, faces)
        geometry_truth = computed(
            metrics.payload(),
            algorithm=ALGORITHM_ID,
            algorithm_version=ALGORITHM_VERSION,
            reason="Deterministic mesh metrics from source tooth geometry.",
        )
        if metrics.principal_directions:
            principal_truth = computed(
                [list(axis) for axis in metrics.principal_directions],
                algorithm=ALGORITHM_ID,
                algorithm_version=ALGORITHM_VERSION,
                reason="Mesh PCA principal directions — not clinical dental axes.",
            )
        else:
            principal_truth = not_available("Insufficient geometry for mesh PCA.")
            quality.append(f"instance {instance_id}: principal directions unavailable.")
    except GeometryMetricsError as error:
        geometry_truth = not_available(f"Geometry metrics unavailable: {error}")
        principal_truth = not_available(f"Geometry metrics unavailable: {error}")
        quality.append(f"instance {instance_id}: {error}")

    crown_truth = computed(
        True,
        algorithm="anatomy_extent_stl",
        algorithm_version="v1",
        reason="Crown mesh present from crown-only STL segmentation.",
    )
    root_truth = not_available("Root/bone geometry requires CBCT or equivalent; not present in STL.")

    landmarks_payload = item.get("landmarks")
    if landmarks_payload:
        # Upstream geometric landmarks exist — still require review for clinical use.
        landmarks_truth = requires_review(
            landmarks_payload,
            reason="Landmarks supplied by upstream geometric method; not clinically verified.",
            algorithm="upstream_landmarks",
        )
    else:
        landmarks_truth = not_available(
            "No landmark coordinates were supplied by an upstream method."
        )

    frame_payload = item.get("coordinate_system") or item.get("movement_reference_frame")
    if frame_payload:
        # Engineering / geometric frames are not clinical dental axes.
        semantics = frame_payload.get("semantics") or []
        is_engineering = any(
            "engineering" in str(item).lower() or "reconstructed" in str(item).lower()
            for item in semantics
        )
        if is_engineering:
            frame_truth = requires_review(
                frame_payload,
                reason=(
                    "Local frame is an engineering/geometric reference, not a validated "
                    "clinical dental coordinate system."
                ),
                algorithm="upstream_frame",
            )
            clinical_axes = not_available(
                "Clinical dental axes are not established from engineering-reference frames."
            )
        else:
            frame_truth = requires_review(
                frame_payload,
                reason="Local coordinate frame present; clinical validation still required.",
                algorithm="upstream_frame",
            )
            clinical_axes = requires_review(
                {
                    "lateral_axis": frame_payload.get("lateral_axis"),
                    "anterior_axis": frame_payload.get("anterior_axis"),
                    "vertical_axis": frame_payload.get("vertical_axis"),
                    "semantics": semantics,
                },
                reason=(
                    "Axes derived from an upstream frame; not automatically promoted to "
                    "verified clinical dental axes."
                ),
                algorithm="upstream_frame",
            )
    else:
        frame_truth = not_available("No local coordinate frame was supplied.")
        clinical_axes = not_available(
            "Clinical dental axes are not available; mesh PCA is reported separately."
        )

    if not vertices or not faces:
        quality.append(f"instance {instance_id}: missing mesh.")
    if arch is None:
        quality.append(f"instance {instance_id}: missing arch.")
    if fixture:
        quality.append(f"instance {instance_id}: fixture/test provenance.")

    # Overall tooth truth: never VERIFIED merely because code ran.
    if geometry_truth.state is IntelligenceTruthState.NOT_AVAILABLE:
        overall = IntelligenceTruthState.NOT_AVAILABLE
    elif fdi_truth.state is IntelligenceTruthState.NOT_AVAILABLE:
        overall = IntelligenceTruthState.REQUIRES_REVIEW
    else:
        overall = IntelligenceTruthState.REQUIRES_REVIEW

    return ToothIntelligence(
        instance_id=instance_id,
        tooth_ref=tooth_ref,
        arch=arch,
        fdi_number=fdi_truth,
        semantic_label=semantic_truth,
        identification_status=item.get("identification_status"),
        identification_confidence=confidence,
        geometry=geometry_truth,
        crown_geometry=crown_truth,
        root_geometry=root_truth,
        landmarks=landmarks_truth,
        local_coordinate_frame=frame_truth,
        clinical_dental_axes=clinical_axes,
        mesh_principal_directions=principal_truth,
        quality_findings=tuple(quality),
        overall_truth_state=overall,
        provenance=provenance,
        fixture=fixture,
        source_mesh_path=source_mesh_path,
        source_mesh_sha256=source_mesh_sha256,
        model_name=model_name,
        model_version=model_version,
    )


def _capability_readiness(
    teeth: list[ToothIntelligence],
    arches: list[ArchIntelligence],
    findings: list[str],
    *,
    occlusion_state: IntelligenceTruthState | None = None,
) -> CapabilityReadiness:
    reasons: list[str] = []
    if not teeth:
        reasons.append("No tooth instances available.")
        unavailable = IntelligenceTruthState.NOT_AVAILABLE
        return CapabilityReadiness(
            identity_readiness=unavailable,
            geometry_readiness=unavailable,
            axis_readiness=unavailable,
            occlusion_readiness=unavailable,
            treatment_setup_readiness=unavailable,
            validation_readiness=unavailable,
            reasons=tuple(reasons),
        )

    unresolved = sum(
        1 for tooth in teeth if tooth.fdi_number.state is IntelligenceTruthState.NOT_AVAILABLE
    )
    has_refs = all(tooth.tooth_ref for tooth in teeth)
    geometry_ok = sum(
        1 for tooth in teeth if tooth.geometry.state is IntelligenceTruthState.COMPUTED
    )
    clinical_axes = sum(
        1
        for tooth in teeth
        if tooth.clinical_dental_axes.state
        in (IntelligenceTruthState.VERIFIED, IntelligenceTruthState.COMPUTED)
    )

    if unresolved == len(teeth):
        identity = IntelligenceTruthState.REQUIRES_REVIEW
        reasons.append("No clinical FDI resolved; stable tooth_ref identity only.")
    elif unresolved > 0:
        identity = IntelligenceTruthState.REQUIRES_REVIEW
        reasons.append(f"{unresolved} teeth lack clinical FDI.")
    else:
        identity = IntelligenceTruthState.REQUIRES_REVIEW
        reasons.append("FDI values require doctor review before clinical use.")

    if geometry_ok == 0:
        geometry = IntelligenceTruthState.NOT_AVAILABLE
        reasons.append("No usable tooth geometry metrics.")
    elif geometry_ok < len(teeth):
        geometry = IntelligenceTruthState.REQUIRES_REVIEW
        reasons.append(f"Geometry metrics incomplete ({geometry_ok}/{len(teeth)}).")
    else:
        geometry = IntelligenceTruthState.COMPUTED

    if clinical_axes == 0:
        axis = IntelligenceTruthState.NOT_AVAILABLE
        reasons.append("Clinical dental axes are not available.")
    else:
        axis = IntelligenceTruthState.REQUIRES_REVIEW
        reasons.append("Clinical dental axes require review.")

    occlusion = occlusion_state or IntelligenceTruthState.NOT_AVAILABLE
    if occlusion is IntelligenceTruthState.NOT_AVAILABLE:
        reasons.append("Occlusion is not available without bite/registration evidence.")
    elif occlusion is IntelligenceTruthState.REQUIRES_REVIEW:
        reasons.append("Occlusion registration/evidence requires doctor review.")
    else:
        reasons.append(
            "Occlusion geometric capability is present; not clinical occlusion approval."
        )

    # Treatment setup is NOT unlocked merely because intelligence objects exist.
    if has_refs and geometry_ok > 0 and len(arches) == 2:
        treatment = IntelligenceTruthState.REQUIRES_REVIEW
        reasons.append(
            "Geometry and semantic identity exist for review; treatment setup is not auto-unlocked."
        )
    else:
        treatment = IntelligenceTruthState.NOT_AVAILABLE
        reasons.append("Treatment setup prerequisites incomplete.")

    # Validation can run on meshes when geometry exists — still not clinical clearance.
    if geometry_ok > 0:
        validation = IntelligenceTruthState.REQUIRES_REVIEW
        reasons.append("Geometric validation may run on meshes; not clinical clearance.")
    else:
        validation = IntelligenceTruthState.NOT_AVAILABLE

    if findings:
        reasons.append(f"Data-quality findings present: {len(findings)}.")

    return CapabilityReadiness(
        identity_readiness=identity,
        geometry_readiness=geometry,
        axis_readiness=axis,
        occlusion_readiness=occlusion,
        treatment_setup_readiness=treatment,
        validation_readiness=validation,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _overall_state(
    teeth: list[ToothIntelligence],
    readiness: CapabilityReadiness,
) -> IntelligenceTruthState:
    if not teeth:
        return IntelligenceTruthState.NOT_AVAILABLE
    if readiness.geometry_readiness is IntelligenceTruthState.NOT_AVAILABLE:
        return IntelligenceTruthState.NOT_AVAILABLE
    return IntelligenceTruthState.REQUIRES_REVIEW
