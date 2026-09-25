"""WP-08 occlusion + advanced anatomy capability engine.

Real anatomical evidence → deterministic processing → explicit provenance →
validation → doctor review. Never fabricates bite registration, contacts, roots,
landmarks, or clinical axes from crown-only or independently oriented arches.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from domain.case.provenance import DataProvenance
from domain.tooth.advanced_anatomy import (
    ADVANCED_ANATOMY_CONTRACT_VERSION,
    AdvancedAnatomyReport,
    AnatomyCapability,
    AnatomyCapabilityKind,
    AnatomyTruthState,
    not_available_capability,
)
from domain.tooth.anatomy_extent import AnatomyExtent, default_anatomy_extent_for_stl
from domain.tooth.intelligence_v2 import IntelligenceTruthState
from domain.tooth.occlusion import (
    OCCLUSION_ALGORITHM_ID,
    OCCLUSION_ALGORITHM_VERSION,
    OCCLUSION_CONTRACT_VERSION,
    REGISTRATION_ALGORITHM_ID,
    ContactSemantics,
    GeometricContactCandidate,
    OcclusionAvailability,
    OcclusionCapabilityReadiness,
    OcclusionCapabilityState,
    OcclusionFreshness,
    OcclusionRepresentation,
    OcclusionResult,
    RegistrationEvidence,
    RegistrationEvidenceKind,
    evaluate_occlusion_freshness,
    no_registration_evidence,
    unavailable_arch_relationship,
    unavailable_occlusion,
)
from domain.treatment_plan.occlusion_anatomy import (
    OcclusionAnatomyBinding,
    OcclusionAnatomyPlan,
    OcclusionAnatomyPrerequisite,
)
from engines.validation.root_bone import root_bone_pathway_supported


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _provenance(value: str | None, *, fixture: bool) -> DataProvenance:
    if fixture:
        return DataProvenance.FIXTURE
    try:
        return DataProvenance(value or "experimental")
    except ValueError:
        return DataProvenance.EXPERIMENTAL


def _arch_hashes(segmentation_record: dict[str, Any]) -> dict[str, str | None]:
    arches = segmentation_record.get("arches") or {}
    out: dict[str, str | None] = {}
    for arch in ("upper", "lower"):
        payload = arches.get(arch) if isinstance(arches, dict) else None
        if isinstance(payload, dict):
            out[arch] = payload.get("source_mesh_sha256")
            out[f"{arch}_path"] = payload.get("source_mesh_path")
        else:
            out[arch] = None
            out[f"{arch}_path"] = None
    return out


def parse_registration_evidence(
    raw: dict[str, Any] | None,
    *,
    provenance: DataProvenance,
    fixture: bool,
    upper_source_artifact: str | None,
    lower_source_artifact: str | None,
    upper_source_hash: str | None,
    lower_source_hash: str | None,
    generated_at: str,
) -> RegistrationEvidence:
    """Accept only explicit registration evidence; never invent from dual-arch presence."""
    if not raw or not isinstance(raw, dict):
        return no_registration_evidence(
            provenance=provenance,
            fixture=fixture,
            upper_source_artifact=upper_source_artifact,
            lower_source_artifact=lower_source_artifact,
            upper_source_hash=upper_source_hash,
            lower_source_hash=lower_source_hash,
            generated_at=generated_at,
        )

    kind_raw = str(raw.get("evidence_kind") or "").strip().lower()
    try:
        kind = RegistrationEvidenceKind(kind_raw)
    except ValueError:
        return no_registration_evidence(
            provenance=provenance,
            fixture=fixture,
            upper_source_artifact=upper_source_artifact,
            lower_source_artifact=lower_source_artifact,
            upper_source_hash=upper_source_hash,
            lower_source_hash=lower_source_hash,
            generated_at=generated_at,
            reason=(
                f"Unrecognized registration evidence_kind={kind_raw!r}; "
                "occlusion remains unavailable."
            ),
        )

    if kind is RegistrationEvidenceKind.NONE:
        return no_registration_evidence(
            provenance=provenance,
            fixture=fixture,
            upper_source_artifact=upper_source_artifact,
            lower_source_artifact=lower_source_artifact,
            upper_source_hash=upper_source_hash,
            lower_source_hash=lower_source_hash,
            generated_at=generated_at,
        )

    transform = raw.get("transform_4x4")
    transform_tuple: tuple[tuple[float, ...], ...] | None = None
    if transform is not None:
        try:
            rows = tuple(tuple(float(v) for v in row) for row in transform)
            if len(rows) != 4 or any(len(row) != 4 for row in rows):
                raise ValueError("transform must be 4x4")
            transform_tuple = rows
        except (TypeError, ValueError):
            return no_registration_evidence(
                provenance=provenance,
                fixture=fixture,
                upper_source_artifact=upper_source_artifact,
                lower_source_artifact=lower_source_artifact,
                upper_source_hash=upper_source_hash,
                lower_source_hash=lower_source_hash,
                generated_at=generated_at,
                reason="Registration transform is malformed; occlusion remains unavailable.",
            )

    method = raw.get("method")
    method_version = raw.get("method_version")
    if not method or not method_version:
        return RegistrationEvidence(
            evidence_kind=kind,
            truth_state=OcclusionCapabilityState.REQUIRES_REVIEW,
            upper_source_artifact=raw.get("upper_source_artifact") or upper_source_artifact,
            lower_source_artifact=raw.get("lower_source_artifact") or lower_source_artifact,
            upper_source_hash=raw.get("upper_source_hash") or upper_source_hash,
            lower_source_hash=raw.get("lower_source_hash") or lower_source_hash,
            transform_4x4=transform_tuple,
            transform_applies_to=raw.get("transform_applies_to"),
            method=method,
            method_version=method_version,
            quality_metric=raw.get("quality_metric"),
            quality_metric_kind=raw.get("quality_metric_kind"),
            quality_established=False,
            registration_version_id=raw.get("registration_version_id"),
            generated_at=raw.get("generated_at") or generated_at,
            provenance=provenance,
            fixture=fixture,
            limitations=(
                "Registration evidence lacks method/version provenance; requires review.",
            ),
            notes=("Incomplete registration provenance.",),
        )

    quality_metric = raw.get("quality_metric")
    quality_kind = raw.get("quality_metric_kind")
    quality_established = bool(
        raw.get("quality_established")
        and quality_metric is not None
        and quality_kind
    )
    # Never fabricate quality numbers — only accept when explicitly supplied.
    if quality_metric is not None and not quality_kind:
        quality_established = False

    if not quality_established:
        truth = OcclusionCapabilityState.REQUIRES_REVIEW
        limitations = (
            "Registration quality/error metrics are not established; requires review.",
            "Do not promote to verified without a documented quality gate.",
        )
    else:
        truth = OcclusionCapabilityState.SOURCE_REGISTERED
        limitations = (
            "Source registration accepted with supplied quality metrics; "
            "not clinical occlusion approval.",
        )

    return RegistrationEvidence(
        evidence_kind=kind,
        truth_state=truth,
        upper_source_artifact=raw.get("upper_source_artifact") or upper_source_artifact,
        lower_source_artifact=raw.get("lower_source_artifact") or lower_source_artifact,
        upper_source_hash=raw.get("upper_source_hash") or upper_source_hash,
        lower_source_hash=raw.get("lower_source_hash") or lower_source_hash,
        transform_4x4=transform_tuple,
        transform_applies_to=raw.get("transform_applies_to"),
        method=str(method),
        method_version=str(method_version),
        quality_metric=float(quality_metric) if quality_metric is not None else None,
        quality_metric_kind=str(quality_kind) if quality_kind else None,
        quality_established=quality_established,
        registration_version_id=raw.get("registration_version_id"),
        generated_at=raw.get("generated_at") or generated_at,
        provenance=provenance,
        fixture=fixture,
        limitations=limitations,
        notes=tuple(raw.get("notes") or ()),
    )


def _candidate_id(
    upper_ref: str | None,
    lower_ref: str | None,
    upper_id: int | None,
    lower_id: int | None,
) -> str:
    material = f"{upper_ref}|{lower_ref}|{upper_id}|{lower_id}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def compute_geometric_contact_candidates(
    *,
    upper_teeth: list[dict[str, Any]],
    lower_teeth: list[dict[str, Any]],
    registration: RegistrationEvidence,
    technical_proximity_threshold: float | None,
    provenance: DataProvenance,
    fixture: bool,
) -> tuple[GeometricContactCandidate, ...]:
    """Compute inter-arch geometric proximity when genuine registration exists.

    Uses centroid-to-centroid distance as a technical geometric signal only.
    Requires an explicit caller-supplied technical threshold — never invents one.
    Does not claim clinical occlusal contacts or diagnoses.
    """
    if registration.truth_state is OcclusionCapabilityState.UNAVAILABLE:
        return ()
    if technical_proximity_threshold is None:
        return ()
    if not (technical_proximity_threshold >= 0 and technical_proximity_threshold == technical_proximity_threshold):
        return ()

    # Preserve source geometry: apply registration transform only to lower centroids
    # for measurement, never mutating source meshes.
    transform = registration.transform_4x4
    candidates: list[GeometricContactCandidate] = []
    for upper in upper_teeth:
        u_cent = upper.get("centroid")
        if not u_cent or len(u_cent) != 3:
            continue
        ux, uy, uz = float(u_cent[0]), float(u_cent[1]), float(u_cent[2])
        for lower in lower_teeth:
            l_cent = lower.get("centroid")
            if not l_cent or len(l_cent) != 3:
                continue
            ox, oy, oz = float(l_cent[0]), float(l_cent[1]), float(l_cent[2])
            lx, ly, lz = ox, oy, oz
            if transform is not None and registration.transform_applies_to == "lower_into_upper":
                # Homogeneous multiply: apply registration to lower centroid only.
                # Source meshes are never mutated.
                row0, row1, row2, row3 = transform
                w = row3[0] * ox + row3[1] * oy + row3[2] * oz + row3[3]
                if abs(w) < 1e-12:
                    continue
                lx = (row0[0] * ox + row0[1] * oy + row0[2] * oz + row0[3]) / w
                ly = (row1[0] * ox + row1[1] * oy + row1[2] * oz + row1[3]) / w
                lz = (row2[0] * ox + row2[1] * oy + row2[2] * oz + row2[3]) / w
            distance = ((ux - lx) ** 2 + (uy - ly) ** 2 + (uz - lz) ** 2) ** 0.5
            if distance > technical_proximity_threshold:
                continue
            # Geometric proximity/contact candidates only — never clinical diagnosis.
            semantics = (
                ContactSemantics.CANDIDATE_CONTACT
                if distance <= technical_proximity_threshold * 0.25
                else ContactSemantics.GEOMETRIC_PROXIMITY
            )
            upper_ref = upper.get("tooth_ref")
            lower_ref = lower.get("tooth_ref")
            upper_id = upper.get("instance_id")
            lower_id = lower.get("instance_id")
            candidates.append(
                GeometricContactCandidate(
                    candidate_id=_candidate_id(upper_ref, lower_ref, upper_id, lower_id),
                    upper_tooth_ref=upper_ref,
                    lower_tooth_ref=lower_ref,
                    upper_instance_id=upper_id,
                    lower_instance_id=lower_id,
                    distance=distance,
                    unit="model units",
                    semantics=semantics,
                    method=OCCLUSION_ALGORITHM_ID,
                    method_version=OCCLUSION_ALGORITHM_VERSION,
                    technical_threshold=technical_proximity_threshold,
                    technical_threshold_kind="caller_supplied_geometric_proximity",
                    truth_state=OcclusionCapabilityState.REQUIRES_REVIEW,
                    clinical_interpretation=None,
                    limitations=(
                        "Centroid-distance geometric proximity is not a clinical occlusal contact.",
                        "Unit is 'model units' — not claimed as millimetres unless calibrated.",
                        "Threshold is a technical geometry threshold, not a clinical threshold.",
                    ),
                    provenance=provenance,
                    fixture=fixture,
                )
            )
    candidates.sort(key=lambda item: (item.upper_tooth_ref or "", item.lower_tooth_ref or "", item.candidate_id))
    return tuple(candidates)


def _tooth_centroids_from_segmentation(
    segmentation_record: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    arches = segmentation_record.get("arches") or {}
    upper: list[dict[str, Any]] = []
    lower: list[dict[str, Any]] = []
    for arch_name, bucket in (("upper", upper), ("lower", lower)):
        payload = arches.get(arch_name) if isinstance(arches, dict) else None
        if not isinstance(payload, dict):
            continue
        for item in payload.get("tooth_instances") or []:
            if not isinstance(item, dict):
                continue
            vertices = item.get("vertices") or []
            if not vertices:
                continue
            xs = [float(v[0]) for v in vertices]
            ys = [float(v[1]) for v in vertices]
            zs = [float(v[2]) for v in vertices]
            n = len(xs)
            centroid = (sum(xs) / n, sum(ys) / n, sum(zs) / n)
            bucket.append(
                {
                    "instance_id": item.get("instance_id"),
                    "tooth_ref": item.get("tooth_ref"),
                    "centroid": centroid,
                }
            )
    return upper, lower


def build_occlusion_result(
    *,
    case_id: str,
    segmentation_record: dict[str, Any],
    registration_raw: dict[str, Any] | None = None,
    technical_proximity_threshold: float | None = None,
    bound_setup_version_id: str | None = None,
    bound_staging_version_id: str | None = None,
    current_setup_version_id: str | None = None,
    current_staging_version_id: str | None = None,
    previous_result: OcclusionResult | None = None,
    generated_at: str | None = None,
) -> OcclusionResult:
    """Build occlusion capability for a case. Defaults to unavailable without evidence."""
    started = perf_counter()
    fixture = bool(segmentation_record.get("processing_mode") == "test_fixture") or bool(
        segmentation_record.get("fixture")
    )
    provenance = _provenance(segmentation_record.get("provenance"), fixture=fixture)
    generated_at = generated_at or _now()
    hashes = _arch_hashes(segmentation_record)
    upper_hash = hashes.get("upper")
    lower_hash = hashes.get("lower")
    upper_path = hashes.get("upper_path")
    lower_path = hashes.get("lower_path")

    # Prefer explicit registration on the segmentation record when not passed.
    if registration_raw is None:
        registration_raw = segmentation_record.get("arch_registration") or segmentation_record.get(
            "bite_registration"
        )

    reg_started = perf_counter()
    registration = parse_registration_evidence(
        registration_raw if isinstance(registration_raw, dict) else None,
        provenance=provenance,
        fixture=fixture,
        upper_source_artifact=upper_path if isinstance(upper_path, str) else None,
        lower_source_artifact=lower_path if isinstance(lower_path, str) else None,
        upper_source_hash=upper_hash if isinstance(upper_hash, str) else None,
        lower_source_hash=lower_hash if isinstance(lower_hash, str) else None,
        generated_at=generated_at,
    )
    registration_ms = (perf_counter() - reg_started) * 1000

    contact_started = perf_counter()
    contact_candidates: tuple[GeometricContactCandidate, ...] = ()
    if registration.truth_state in (
        OcclusionCapabilityState.SOURCE_REGISTERED,
        OcclusionCapabilityState.REQUIRES_REVIEW,
        OcclusionCapabilityState.COMPUTED,
    ) and registration.evidence_kind is not RegistrationEvidenceKind.NONE:
        if technical_proximity_threshold is not None:
            upper_teeth, lower_teeth = _tooth_centroids_from_segmentation(segmentation_record)
            contact_candidates = compute_geometric_contact_candidates(
                upper_teeth=upper_teeth,
                lower_teeth=lower_teeth,
                registration=registration,
                technical_proximity_threshold=technical_proximity_threshold,
                provenance=provenance,
                fixture=fixture,
            )
    contact_ms = (perf_counter() - contact_started) * 1000

    arch_relationship = unavailable_arch_relationship()

    if registration.truth_state is OcclusionCapabilityState.UNAVAILABLE:
        capability_state = OcclusionCapabilityState.UNAVAILABLE
        representation = unavailable_occlusion(provenance=provenance, fixture=fixture)
        algorithm = REGISTRATION_ALGORITHM_ID
        algorithm_version = None
        geometric_contacts_state = OcclusionCapabilityState.UNAVAILABLE
        limitations = (
            "Occlusion is not available without genuine bite/registration evidence.",
            "Independent upper/lower crown STLs do not establish occlusion.",
            "Geometric proximity was not computed because registration is unavailable.",
            "No clinical occlusal diagnosis is produced.",
        )
    elif registration.truth_state is OcclusionCapabilityState.REQUIRES_REVIEW:
        capability_state = OcclusionCapabilityState.REQUIRES_REVIEW
        representation = OcclusionRepresentation(
            availability=OcclusionAvailability.REQUIRES_REVIEW,
            upper_lower_registration=OcclusionAvailability.REQUIRES_REVIEW,
            occlusal_relationship=OcclusionAvailability.UNAVAILABLE,
            bite_record=(
                OcclusionAvailability.REQUIRES_REVIEW
                if registration.evidence_kind is RegistrationEvidenceKind.BITE_SCAN
                else OcclusionAvailability.UNAVAILABLE
            ),
            occlusal_contacts=(
                OcclusionAvailability.REQUIRES_REVIEW
                if contact_candidates
                else OcclusionAvailability.UNAVAILABLE
            ),
            contact_count=len(contact_candidates) if contact_candidates else None,
            notes=(
                "Registration evidence present but incomplete or quality not established.",
                "Geometric contact candidates require doctor review when present.",
            ),
            provenance=provenance,
            fixture=fixture,
        )
        algorithm = OCCLUSION_ALGORITHM_ID if contact_candidates else REGISTRATION_ALGORITHM_ID
        algorithm_version = OCCLUSION_ALGORITHM_VERSION if contact_candidates else None
        geometric_contacts_state = (
            OcclusionCapabilityState.REQUIRES_REVIEW
            if contact_candidates
            else OcclusionCapabilityState.UNAVAILABLE
        )
        limitations = registration.limitations + (
            "Geometric contact candidates are not clinical occlusal contacts.",
            "Arch relationship clinical diagnoses remain unavailable.",
        )
    else:
        # SOURCE_REGISTERED (or theoretically COMPUTED after proximity)
        if contact_candidates:
            capability_state = OcclusionCapabilityState.COMPUTED
            contacts_avail = OcclusionAvailability.COMPUTED
            geometric_contacts_state = OcclusionCapabilityState.COMPUTED
        else:
            capability_state = OcclusionCapabilityState.SOURCE_REGISTERED
            contacts_avail = OcclusionAvailability.UNAVAILABLE
            geometric_contacts_state = OcclusionCapabilityState.UNAVAILABLE
        representation = OcclusionRepresentation(
            availability=(
                OcclusionAvailability.COMPUTED
                if capability_state is OcclusionCapabilityState.COMPUTED
                else OcclusionAvailability.REQUIRES_REVIEW
            ),
            upper_lower_registration=OcclusionAvailability.COMPUTED,
            occlusal_relationship=OcclusionAvailability.UNAVAILABLE,
            bite_record=(
                OcclusionAvailability.COMPUTED
                if registration.evidence_kind is RegistrationEvidenceKind.BITE_SCAN
                else OcclusionAvailability.UNAVAILABLE
            ),
            occlusal_contacts=contacts_avail,
            contact_count=len(contact_candidates) if contact_candidates else None,
            notes=(
                "Source registration accepted; geometric contacts are technical findings only.",
                "Not equivalent to clinical occlusion approval.",
            ),
            provenance=provenance,
            fixture=fixture,
        )
        algorithm = OCCLUSION_ALGORITHM_ID if contact_candidates else REGISTRATION_ALGORITHM_ID
        algorithm_version = OCCLUSION_ALGORITHM_VERSION if contact_candidates else registration.method_version
        limitations = registration.limitations + (
            "Geometric proximity/contact is not a clinical occlusal diagnosis.",
            "Class I/II/III and OJ/OB are not inferred.",
        )

    # Fresh build against current hashes is CURRENT; prior result detects source/version drift.
    if previous_result is None:
        freshness = OcclusionFreshness.CURRENT
    else:
        freshness = evaluate_occlusion_freshness(
            bound_upper_hash=previous_result.bound_upper_hash,
            bound_lower_hash=previous_result.bound_lower_hash,
            current_upper_hash=upper_hash if isinstance(upper_hash, str) else None,
            current_lower_hash=lower_hash if isinstance(lower_hash, str) else None,
            bound_registration_version_id=previous_result.bound_registration_version_id,
            current_registration_version_id=registration.registration_version_id,
            bound_setup_version_id=previous_result.bound_setup_version_id,
            current_setup_version_id=current_setup_version_id,
            bound_staging_version_id=previous_result.bound_staging_version_id,
            current_staging_version_id=current_staging_version_id,
            has_result=True,
        )

    readiness = OcclusionCapabilityReadiness(
        registration=registration.truth_state,
        occlusion=capability_state,
        geometric_contacts=geometric_contacts_state,
        arch_relationship=arch_relationship.truth_state,
        doctor_review_required=capability_state
        in (
            OcclusionCapabilityState.REQUIRES_REVIEW,
            OcclusionCapabilityState.COMPUTED,
            OcclusionCapabilityState.SOURCE_REGISTERED,
        ),
        notes=(
            "Occlusion capability gates are not clinical approval.",
            "Unavailable occlusion does not block unrelated planning workflows.",
        ),
    )

    total_ms = (perf_counter() - started) * 1000
    return OcclusionResult(
        contract_version=OCCLUSION_CONTRACT_VERSION,
        case_id=case_id,
        capability_state=capability_state,
        representation=representation,
        registration=registration,
        contact_candidates=contact_candidates,
        arch_relationship=arch_relationship,
        readiness=readiness,
        freshness=freshness,
        bound_source_input_hash=segmentation_record.get("input_hash"),
        bound_upper_hash=upper_hash if isinstance(upper_hash, str) else None,
        bound_lower_hash=lower_hash if isinstance(lower_hash, str) else None,
        bound_registration_version_id=registration.registration_version_id,
        bound_setup_version_id=bound_setup_version_id,
        bound_staging_version_id=bound_staging_version_id,
        generated_at=generated_at,
        algorithm=algorithm,
        algorithm_version=algorithm_version,
        provenance=provenance,
        fixture=fixture,
        limitations=limitations,
        timings_ms={
            "registration_ms": registration_ms,
            "contact_proximity_ms": contact_ms,
            "total_ms": total_ms,
        },
        technical_threshold=technical_proximity_threshold,
        technical_threshold_kind=(
            "caller_supplied_geometric_proximity"
            if technical_proximity_threshold is not None
            else None
        ),
        technical_threshold_version=(
            OCCLUSION_ALGORITHM_VERSION if technical_proximity_threshold is not None else None
        ),
    )


def _count_geometry_signals(segmentation_record: dict[str, Any]) -> dict[str, int]:
    arches = segmentation_record.get("arches") or {}
    crown = 0
    landmark = 0
    clinical_axes = 0
    geometric_axes = 0
    for arch_name in ("upper", "lower"):
        payload = arches.get(arch_name) if isinstance(arches, dict) else None
        if not isinstance(payload, dict):
            continue
        for item in payload.get("tooth_instances") or []:
            if not isinstance(item, dict):
                continue
            verts = item.get("vertices") or []
            faces = item.get("faces") or []
            if verts and faces:
                crown += 1
            if item.get("landmarks"):
                landmark += 1
            frame = item.get("coordinate_system") or item.get("movement_reference_frame")
            if frame:
                # Upstream engineering frame ≠ clinical axes (WP-02).
                geometric_axes += 1
            if item.get("clinical_dental_axes"):
                clinical_axes += 1
    return {
        "crown": crown,
        "landmark": landmark,
        "clinical_axes": clinical_axes,
        "geometric_axes": geometric_axes,
    }


def build_advanced_anatomy_report(
    *,
    case_id: str,
    segmentation_record: dict[str, Any],
    tooth_intelligence_summaries: list[dict[str, Any]] | None = None,
    generated_at: str | None = None,
) -> AdvancedAnatomyReport:
    """Honest advanced-anatomy capability report from source evidence only."""
    started = perf_counter()
    fixture = bool(segmentation_record.get("processing_mode") == "test_fixture") or bool(
        segmentation_record.get("fixture")
    )
    provenance = _provenance(segmentation_record.get("provenance"), fixture=fixture)
    generated_at = generated_at or _now()
    hashes = _arch_hashes(segmentation_record)
    extent = default_anatomy_extent_for_stl()
    anatomy_extent_raw = segmentation_record.get("anatomy_extent")
    if anatomy_extent_raw == AnatomyExtent.ROOT_BONE_CBCT.value:
        extent = AnatomyExtent.ROOT_BONE_CBCT

    signals = _count_geometry_signals(segmentation_record)
    # Prefer explicit intelligence summaries when provided (more precise truth).
    if tooth_intelligence_summaries:
        crown = sum(
            1
            for t in tooth_intelligence_summaries
            if (t.get("crown_geometry") or {}).get("state")
            in (IntelligenceTruthState.COMPUTED.value, IntelligenceTruthState.VERIFIED.value)
        )
        root = sum(
            1
            for t in tooth_intelligence_summaries
            if (t.get("root_geometry") or {}).get("state")
            in (IntelligenceTruthState.COMPUTED.value, IntelligenceTruthState.VERIFIED.value)
        )
        landmarks = sum(
            1
            for t in tooth_intelligence_summaries
            if (t.get("landmarks") or {}).get("state")
            in (IntelligenceTruthState.COMPUTED.value, IntelligenceTruthState.VERIFIED.value)
        )
        clinical_axes = sum(
            1
            for t in tooth_intelligence_summaries
            if (t.get("clinical_dental_axes") or {}).get("state")
            in (IntelligenceTruthState.COMPUTED.value, IntelligenceTruthState.VERIFIED.value)
        )
        geometric_axes = sum(
            1
            for t in tooth_intelligence_summaries
            if (t.get("mesh_principal_directions") or {}).get("state")
            == IntelligenceTruthState.COMPUTED.value
        )
    else:
        crown = signals["crown"]
        root = 0
        landmarks = signals["landmark"]
        clinical_axes = signals["clinical_axes"]
        geometric_axes = signals["geometric_axes"]

    caps: list[AnatomyCapability] = []
    source_artifact = hashes.get("upper_path") or hashes.get("lower_path")
    source_hash = hashes.get("upper") or hashes.get("lower")

    if crown > 0:
        caps.append(
            AnatomyCapability(
                kind=AnatomyCapabilityKind.CROWN_GEOMETRY,
                truth_state=AnatomyTruthState.COMPUTED,
                source="surface_mesh",
                source_artifact=source_artifact if isinstance(source_artifact, str) else None,
                source_hash=source_hash if isinstance(source_hash, str) else None,
                algorithm="crown_surface_presence",
                algorithm_version="anatomy_gate_v1",
                generated_at=generated_at,
                limitations=("Crown surface geometry from STL; not root/bone anatomy.",),
                provenance=provenance,
                clinical=False,
                notes=(f"{crown} tooth instances expose crown surface geometry.",),
                value={"tooth_instance_count": crown},
            )
        )
        crown_state = AnatomyTruthState.COMPUTED
    else:
        caps.append(
            not_available_capability(
                AnatomyCapabilityKind.CROWN_GEOMETRY,
                reason="No crown surface geometry is available.",
                provenance=provenance,
                clinical=False,
                generated_at=generated_at,
            )
        )
        crown_state = AnatomyTruthState.NOT_AVAILABLE

    if root > 0 and root_bone_pathway_supported(extent):
        root_state = AnatomyTruthState.REQUIRES_REVIEW
        caps.append(
            AnatomyCapability(
                kind=AnatomyCapabilityKind.ROOT_GEOMETRY,
                truth_state=root_state,
                source="cbct_or_root_mesh",
                source_artifact=source_artifact if isinstance(source_artifact, str) else None,
                source_hash=source_hash if isinstance(source_hash, str) else None,
                algorithm="root_geometry_presence",
                algorithm_version="anatomy_gate_v1",
                generated_at=generated_at,
                limitations=("Root geometry requires genuine CBCT/root source; review required.",),
                provenance=provenance,
                clinical=True,
                value={"tooth_instance_count": root},
            )
        )
    else:
        root_state = AnatomyTruthState.NOT_AVAILABLE
        caps.append(
            not_available_capability(
                AnatomyCapabilityKind.ROOT_GEOMETRY,
                reason=(
                    "Root geometry is not available for crown-only STL. "
                    "Roots are never fabricated from crowns."
                ),
                provenance=provenance,
                clinical=True,
                source_artifact=source_artifact if isinstance(source_artifact, str) else None,
                source_hash=source_hash if isinstance(source_hash, str) else None,
                generated_at=generated_at,
            )
        )

    if landmarks > 0:
        landmark_state = AnatomyTruthState.REQUIRES_REVIEW
        caps.append(
            AnatomyCapability(
                kind=AnatomyCapabilityKind.LANDMARK_GEOMETRY,
                truth_state=landmark_state,
                source="upstream_landmarks",
                source_artifact=source_artifact if isinstance(source_artifact, str) else None,
                source_hash=source_hash if isinstance(source_hash, str) else None,
                algorithm="landmark_presence",
                algorithm_version="anatomy_gate_v1",
                generated_at=generated_at,
                limitations=(
                    "Landmarks require review; centroids/bounding-box extrema are not clinical landmarks.",
                ),
                provenance=provenance,
                clinical=True,
                value={"tooth_instance_count": landmarks},
            )
        )
    else:
        landmark_state = AnatomyTruthState.NOT_AVAILABLE
        caps.append(
            not_available_capability(
                AnatomyCapabilityKind.LANDMARK_GEOMETRY,
                reason=(
                    "Landmark geometry is not available. "
                    "Centroids and bounding-box extrema are not labeled as clinical landmarks."
                ),
                provenance=provenance,
                clinical=True,
                generated_at=generated_at,
            )
        )

    if clinical_axes > 0:
        clinical_axes_state = AnatomyTruthState.REQUIRES_REVIEW
        caps.append(
            AnatomyCapability(
                kind=AnatomyCapabilityKind.CLINICAL_AXES,
                truth_state=clinical_axes_state,
                source="clinical_axis_definition",
                source_artifact=source_artifact if isinstance(source_artifact, str) else None,
                source_hash=source_hash if isinstance(source_hash, str) else None,
                algorithm="clinical_axes_presence",
                algorithm_version="anatomy_gate_v1",
                generated_at=generated_at,
                limitations=("Clinical dental axes require review; mesh PCA is reported separately.",),
                provenance=provenance,
                clinical=True,
                value={"tooth_instance_count": clinical_axes},
            )
        )
    else:
        clinical_axes_state = AnatomyTruthState.NOT_AVAILABLE
        caps.append(
            not_available_capability(
                AnatomyCapabilityKind.CLINICAL_AXES,
                reason=(
                    "Clinical dental axes are not available. "
                    "Mesh PCA principal directions are never labeled as clinical axes."
                ),
                provenance=provenance,
                clinical=True,
                generated_at=generated_at,
            )
        )

    if geometric_axes > 0 or signals["geometric_axes"] > 0 or crown > 0:
        # Mesh PCA / engineering frames are generic geometric directions.
        geo_count = geometric_axes or signals["geometric_axes"] or crown
        generic_state = AnatomyTruthState.COMPUTED
        caps.append(
            AnatomyCapability(
                kind=AnatomyCapabilityKind.GENERIC_GEOMETRIC_AXES,
                truth_state=generic_state,
                source="mesh_pca_or_engineering_frame",
                source_artifact=source_artifact if isinstance(source_artifact, str) else None,
                source_hash=source_hash if isinstance(source_hash, str) else None,
                algorithm="mesh_pca",
                algorithm_version="mesh_metrics_v1",
                generated_at=generated_at,
                limitations=(
                    "Generic geometric directions (mesh PCA / engineering frames) "
                    "are not clinical dental axes.",
                ),
                provenance=provenance,
                clinical=False,
                notes=(f"{geo_count} instances may expose generic geometric directions.",),
                value={"tooth_instance_count": geo_count, "kind": "mesh_pca"},
            )
        )
    else:
        generic_state = AnatomyTruthState.NOT_AVAILABLE
        caps.append(
            not_available_capability(
                AnatomyCapabilityKind.GENERIC_GEOMETRIC_AXES,
                reason="Generic geometric directions are not available.",
                provenance=provenance,
                clinical=False,
                generated_at=generated_at,
            )
        )

    if root_bone_pathway_supported(extent):
        cbct_state = AnatomyTruthState.REQUIRES_REVIEW
        caps.append(
            AnatomyCapability(
                kind=AnatomyCapabilityKind.CBCT_VOLUMETRIC_ANATOMY,
                truth_state=cbct_state,
                source="cbct_dicom",
                source_artifact=None,
                source_hash=None,
                algorithm="cbct_pathway_gate",
                algorithm_version="anatomy_gate_v1",
                generated_at=generated_at,
                limitations=("CBCT pathway flagged; volumetric structures require validated ingest.",),
                provenance=provenance,
                clinical=True,
            )
        )
    else:
        cbct_state = AnatomyTruthState.NOT_AVAILABLE
        caps.append(
            not_available_capability(
                AnatomyCapabilityKind.CBCT_VOLUMETRIC_ANATOMY,
                reason=(
                    "CBCT/volumetric anatomy is not available. "
                    "No CBCT pathway is invented from surface STL data."
                ),
                provenance=provenance,
                clinical=True,
                generated_at=generated_at,
            )
        )

    total_ms = (perf_counter() - started) * 1000
    return AdvancedAnatomyReport(
        contract_version=ADVANCED_ANATOMY_CONTRACT_VERSION,
        case_id=case_id,
        anatomy_extent=extent,
        capabilities=tuple(caps),
        crown_geometry=crown_state,
        root_geometry=root_state,
        landmark_geometry=landmark_state,
        clinical_axes=clinical_axes_state,
        generic_geometric_axes=generic_state,
        cbct_volumetric_anatomy=cbct_state,
        generated_at=generated_at,
        provenance=provenance,
        fixture=fixture,
        limitations=(
            "Advanced anatomy capabilities declare honesty states; missing anatomy is not fabricated.",
            "Generic geometric directions are never promoted to clinical dental axes.",
            "Root/CBCT anatomy remains not available for crown-only STL.",
        ),
        timings_ms={"anatomy_capability_ms": total_ms},
        source_artifact_hashes={
            "upper": hashes.get("upper") if isinstance(hashes.get("upper"), str) else None,
            "lower": hashes.get("lower") if isinstance(hashes.get("lower"), str) else None,
        },
    )


def _map_occlusion_prerequisite(state: OcclusionCapabilityState) -> OcclusionAnatomyPrerequisite:
    if state is OcclusionCapabilityState.UNAVAILABLE:
        return OcclusionAnatomyPrerequisite.NOT_AVAILABLE
    if state is OcclusionCapabilityState.REQUIRES_REVIEW:
        return OcclusionAnatomyPrerequisite.REQUIRES_REVIEW
    if state in (
        OcclusionCapabilityState.SOURCE_REGISTERED,
        OcclusionCapabilityState.COMPUTED,
        OcclusionCapabilityState.VERIFIED,
    ):
        return OcclusionAnatomyPrerequisite.AVAILABLE
    return OcclusionAnatomyPrerequisite.UNAVAILABLE


def _map_anatomy_prerequisite(state: AnatomyTruthState) -> OcclusionAnatomyPrerequisite:
    if state is AnatomyTruthState.NOT_AVAILABLE:
        return OcclusionAnatomyPrerequisite.NOT_AVAILABLE
    if state is AnatomyTruthState.REQUIRES_REVIEW:
        return OcclusionAnatomyPrerequisite.REQUIRES_REVIEW
    if state in (AnatomyTruthState.COMPUTED, AnatomyTruthState.VERIFIED):
        return OcclusionAnatomyPrerequisite.AVAILABLE
    return OcclusionAnatomyPrerequisite.UNAVAILABLE


def build_occlusion_anatomy_plan(
    *,
    occlusion: OcclusionResult,
    advanced_anatomy: AdvancedAnatomyReport,
    setup_version_id: str | None = None,
    staging_version_id: str | None = None,
) -> OcclusionAnatomyPlan:
    freshness = occlusion.freshness
    if freshness is OcclusionFreshness.STALE:
        occ_prereq = OcclusionAnatomyPrerequisite.STALE
    else:
        occ_prereq = _map_occlusion_prerequisite(occlusion.capability_state)
    return OcclusionAnatomyPlan(
        binding=OcclusionAnatomyBinding(
            source_input_hash=occlusion.bound_source_input_hash,
            upper_hash=occlusion.bound_upper_hash,
            lower_hash=occlusion.bound_lower_hash,
            registration_version_id=occlusion.bound_registration_version_id,
            setup_version_id=setup_version_id or occlusion.bound_setup_version_id,
            staging_version_id=staging_version_id or occlusion.bound_staging_version_id,
        ),
        freshness=freshness,
        occlusion=occlusion,
        advanced_anatomy=advanced_anatomy,
        occlusion_prerequisite=occ_prereq,
        clinical_axes_prerequisite=_map_anatomy_prerequisite(advanced_anatomy.clinical_axes),
        root_geometry_prerequisite=_map_anatomy_prerequisite(advanced_anatomy.root_geometry),
        landmark_prerequisite=_map_anatomy_prerequisite(advanced_anatomy.landmark_geometry),
        notes=(
            "Occlusion prerequisite applies only to occlusion-aware features.",
            "Unrelated treatment planning remains available when occlusion is not available.",
            "Geometric contact candidates are not clinical approval.",
        ),
    )


def intelligence_truth_for_occlusion(
    capability_state: OcclusionCapabilityState,
) -> IntelligenceTruthState:
    if capability_state is OcclusionCapabilityState.UNAVAILABLE:
        return IntelligenceTruthState.NOT_AVAILABLE
    if capability_state is OcclusionCapabilityState.REQUIRES_REVIEW:
        return IntelligenceTruthState.REQUIRES_REVIEW
    if capability_state is OcclusionCapabilityState.VERIFIED:
        return IntelligenceTruthState.VERIFIED
    # source_registered / computed
    return IntelligenceTruthState.COMPUTED


__all__ = [
    "build_advanced_anatomy_report",
    "build_occlusion_anatomy_plan",
    "build_occlusion_result",
    "compute_geometric_contact_candidates",
    "intelligence_truth_for_occlusion",
    "parse_registration_evidence",
]
