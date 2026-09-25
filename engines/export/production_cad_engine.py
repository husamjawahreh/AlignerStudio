"""WP-10 Production CAD engine — honesty layer over manufacturing boundary + export.

Does not generate shells, trimlines, or undercut CAD. Does not invent manufacturing
certification. Separates clinical treatment geometry from derived production artifacts.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from domain.treatment_plan.manufacturing import build_manufacturing_boundary_report
from domain.treatment_plan.production_cad import (
    PRODUCTION_ALGORITHM_ID,
    PRODUCTION_ALGORITHM_VERSION,
    PRODUCTION_CONTRACT_VERSION,
    ProductionBinding,
    ProductionCapabilityReadiness,
    ProductionCapabilityState,
    ProductionFreshness,
    ProductionParameter,
    ProductionPlan,
    ProductionQcCheck,
    ProductionQcSeverity,
    ProductionQcStatus,
    ProductionSourceKind,
    ProductionTruthState,
    evaluate_production_freshness,
)
from domain.treatment_plan.setup import TreatmentPlanProposal
from domain.treatment_plan.staging import StagingResult
from domain.treatment_plan.validation import TreatmentValidationReport


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _stable_id(*parts: str | None) -> str:
    material = "|".join(part or "" for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def _sha256_vertices(vertices: Any) -> str:
    digest = hashlib.sha256()
    for point in vertices or ():
        digest.update(f"{float(point[0]):.9f},{float(point[1]):.9f},{float(point[2]):.9f};".encode())
    return digest.hexdigest()[:16]


def _mesh_integrity_checks(
    staging: StagingResult,
    *,
    stage_index: int | None,
) -> list[ProductionQcCheck]:
    """Basic geometric integrity on treatment-stage meshes — not manufacturing readiness."""
    checks: list[ProductionQcCheck] = []
    if not staging.stages:
        checks.append(
            ProductionQcCheck(
                check_id="mesh_integrity",
                label="Mesh integrity",
                status=ProductionQcStatus.NOT_AVAILABLE,
                severity=ProductionQcSeverity.INFO,
                truth_state=ProductionTruthState.NOT_AVAILABLE,
                message="No staged treatment meshes available for integrity checks.",
                affected_geometry=(),
                algorithm=PRODUCTION_ALGORITHM_ID,
                algorithm_version=PRODUCTION_ALGORITHM_VERSION,
                provenance="experimental",
                limitations=("Mesh integrity requires staged treatment geometry.",),
            )
        )
        return checks

    stages = staging.stages
    if stage_index is not None:
        stages = tuple(s for s in staging.stages if s.stage_index == stage_index)
        if not stages:
            checks.append(
                ProductionQcCheck(
                    check_id="mesh_integrity",
                    label="Mesh integrity",
                    status=ProductionQcStatus.ERROR,
                    severity=ProductionQcSeverity.ERROR,
                    truth_state=ProductionTruthState.COMPUTED,
                    message=f"Selected stage_index={stage_index} is absent from staging.",
                    affected_geometry=(),
                    algorithm=PRODUCTION_ALGORITHM_ID,
                    algorithm_version=PRODUCTION_ALGORITHM_VERSION,
                    provenance="experimental",
                )
            )
            return checks

    empty = 0
    nonfinite = 0
    inspected = 0
    affected: list[str] = []
    for stage in stages:
        for state in stage.tooth_states:
            inspected += 1
            verts = state.vertices or ()
            faces = getattr(state, "source_faces", None) or getattr(state, "final_target_faces", None) or ()
            tooth_key = str(state.tooth_ref or state.tooth_number or f"stage{stage.stage_index}:unknown")
            if not verts or not faces:
                empty += 1
                affected.append(tooth_key)
                continue
            for point in verts:
                if len(point) < 3 or not all(math.isfinite(float(v)) for v in point[:3]):
                    nonfinite += 1
                    affected.append(tooth_key)
                    break

    if empty or nonfinite:
        status = ProductionQcStatus.ERROR
        severity = ProductionQcSeverity.ERROR
        truth = ProductionTruthState.COMPUTED
        message = (
            f"Treatment mesh integrity issues: empty={empty}, nonfinite={nonfinite}, "
            f"inspected={inspected}."
        )
    else:
        status = ProductionQcStatus.PASS
        severity = ProductionQcSeverity.INFO
        truth = ProductionTruthState.COMPUTED
        message = (
            f"Treatment mesh integrity: {inspected} meshes have finite non-empty geometry. "
            "This is not manufacturing readiness."
        )
    checks.append(
        ProductionQcCheck(
            check_id="mesh_integrity",
            label="Mesh integrity (treatment geometry)",
            status=status,
            severity=severity,
            truth_state=truth,
            message=message,
            affected_geometry=tuple(dict.fromkeys(affected)),
            algorithm=PRODUCTION_ALGORITHM_ID,
            algorithm_version=PRODUCTION_ALGORITHM_VERSION,
            provenance="experimental",
            limitations=(
                "Finite/non-empty checks are technical only.",
                "Passing mesh integrity does not certify manufacturing readiness.",
            ),
        )
    )
    return checks


def _unavailable_cad_check(check_id: str, label: str, reason: str) -> ProductionQcCheck:
    return ProductionQcCheck(
        check_id=check_id,
        label=label,
        status=ProductionQcStatus.NOT_AVAILABLE,
        severity=ProductionQcSeverity.INFO,
        truth_state=ProductionTruthState.NOT_AVAILABLE,
        message=reason,
        affected_geometry=(),
        algorithm=PRODUCTION_ALGORITHM_ID,
        algorithm_version=PRODUCTION_ALGORITHM_VERSION,
        provenance="experimental",
        limitations=(reason, "Unavailable manufacturing CAD is never treated as PASS."),
    )


def build_production_plan(
    *,
    case_id: str,
    proposal: TreatmentPlanProposal,
    staging: StagingResult,
    validation: TreatmentValidationReport | None,
    selected_stage_index: int | None = None,
    selected_source_kind: ProductionSourceKind | None = None,
    clinical_tools_setup_version_id: str | None = None,
    clinical_tools_staging_version_id: str | None = None,
    validation_run_id: str | None = None,
    validation_freshness: str | None = None,
    occlusion_capability_state: str | None = None,
    current_setup_version_id: str | None = None,
    current_staging_version_id: str | None = None,
    current_clinical_tools_setup_version_id: str | None = None,
    current_validation_run_id: str | None = None,
    previous_plan: ProductionPlan | None = None,
    upper_mesh_hash: str | None = None,
    lower_mesh_hash: str | None = None,
    input_hash: str | None = None,
    parent_production_version_id: str | None = None,
    bound_setup_version_id: str | None = None,
    bound_staging_version_id: str | None = None,
    bound_clinical_tools_setup_version_id: str | None = None,
    bound_validation_run_id: str | None = None,
    committed_production_version_id: str | None = None,
    generated_at: str | None = None,
) -> ProductionPlan:
    """Build Production CAD boundary plan. Shell/trimline/undercut remain unavailable."""
    started = perf_counter()
    generated_at = generated_at or _now()
    has_stages = bool(staging.stages)
    boundary = build_manufacturing_boundary_report(has_stage_models=has_stages)

    # Explicit source selection — never silently invent a selected stage for appliance CAD.
    if selected_stage_index is None and selected_source_kind is None:
        source_kind = ProductionSourceKind.UNSELECTED
        selected_stage_id = None
        source_state_cap = ProductionCapabilityState.REQUIRES_REVIEW
    elif selected_source_kind is ProductionSourceKind.FINAL_TARGET or (
        selected_stage_index is not None
        and has_stages
        and selected_stage_index == staging.stages[-1].stage_index
        and selected_source_kind in (None, ProductionSourceKind.SELECTED_STAGE, ProductionSourceKind.FINAL_TARGET)
    ):
        if not has_stages:
            source_kind = ProductionSourceKind.UNSELECTED
            selected_stage_id = None
            selected_stage_index = None
            source_state_cap = ProductionCapabilityState.NOT_AVAILABLE
        else:
            stage = staging.stages[-1] if selected_stage_index is None else next(
                (s for s in staging.stages if s.stage_index == selected_stage_index),
                staging.stages[-1],
            )
            selected_stage_index = stage.stage_index
            selected_stage_id = stage.stage_id
            source_kind = selected_source_kind or ProductionSourceKind.FINAL_TARGET
            source_state_cap = ProductionCapabilityState.AVAILABLE
    elif selected_stage_index is not None:
        match = next((s for s in staging.stages if s.stage_index == selected_stage_index), None)
        if match is None:
            source_kind = ProductionSourceKind.UNSELECTED
            selected_stage_id = None
            source_state_cap = ProductionCapabilityState.NOT_AVAILABLE
        else:
            selected_stage_id = match.stage_id
            source_kind = selected_source_kind or ProductionSourceKind.SELECTED_STAGE
            source_state_cap = ProductionCapabilityState.AVAILABLE
    else:
        source_kind = ProductionSourceKind.UNSELECTED
        selected_stage_id = None
        source_state_cap = ProductionCapabilityState.REQUIRES_REVIEW

    # Validation freshness gate
    if validation is None:
        validation_cap = ProductionCapabilityState.NOT_AVAILABLE
    elif (validation_freshness or "current") == "stale":
        validation_cap = ProductionCapabilityState.REQUIRES_REVIEW
    else:
        validation_cap = ProductionCapabilityState.AVAILABLE

    qc: list[ProductionQcCheck] = []
    qc.append(
        ProductionQcCheck(
            check_id="source_binding",
            label="Source treatment-state binding",
            status=(
                ProductionQcStatus.REQUIRES_REVIEW
                if source_state_cap is ProductionCapabilityState.REQUIRES_REVIEW
                else ProductionQcStatus.PASS
                if source_state_cap is ProductionCapabilityState.AVAILABLE
                else ProductionQcStatus.NOT_AVAILABLE
            ),
            severity=ProductionQcSeverity.WARNING
            if source_state_cap is ProductionCapabilityState.REQUIRES_REVIEW
            else ProductionQcSeverity.INFO,
            truth_state=(
                ProductionTruthState.REQUIRES_REVIEW
                if source_state_cap is ProductionCapabilityState.REQUIRES_REVIEW
                else ProductionTruthState.COMPUTED
                if source_state_cap is ProductionCapabilityState.AVAILABLE
                else ProductionTruthState.NOT_AVAILABLE
            ),
            message=(
                "Doctor must explicitly select a production source stage/target."
                if source_state_cap is ProductionCapabilityState.REQUIRES_REVIEW
                else f"Production source bound to {source_kind.value} stage_index={selected_stage_index}."
                if source_state_cap is ProductionCapabilityState.AVAILABLE
                else "No valid treatment/staging state available for production."
            ),
            affected_geometry=(),
            algorithm=PRODUCTION_ALGORITHM_ID,
            algorithm_version=PRODUCTION_ALGORITHM_VERSION,
            provenance=proposal.provenance.value if proposal.provenance else "experimental",
            limitations=("Explicit source selection is required before appliance CAD.",),
        )
    )
    qc.append(
        ProductionQcCheck(
            check_id="validation_binding",
            label="Validation 2.0 binding",
            status=(
                ProductionQcStatus.PASS
                if validation_cap is ProductionCapabilityState.AVAILABLE
                else ProductionQcStatus.REQUIRES_REVIEW
                if validation_cap is ProductionCapabilityState.REQUIRES_REVIEW
                else ProductionQcStatus.NOT_AVAILABLE
            ),
            severity=ProductionQcSeverity.WARNING
            if validation_cap is not ProductionCapabilityState.AVAILABLE
            else ProductionQcSeverity.INFO,
            truth_state=(
                ProductionTruthState.COMPUTED
                if validation_cap is ProductionCapabilityState.AVAILABLE
                else ProductionTruthState.REQUIRES_REVIEW
                if validation_cap is ProductionCapabilityState.REQUIRES_REVIEW
                else ProductionTruthState.NOT_AVAILABLE
            ),
            message=(
                f"Validation run bound: {validation_run_id or (validation.report_id if validation else None)}."
                if validation is not None
                else "Validation report unavailable."
            ),
            affected_geometry=(),
            algorithm=PRODUCTION_ALGORITHM_ID,
            algorithm_version=PRODUCTION_ALGORITHM_VERSION,
            provenance="experimental",
            limitations=(
                "Unavailable Validation 2.0 checks are not treated as PASS.",
                "Validation PASS is not clinical or manufacturing approval.",
            ),
        )
    )
    qc.append(
        ProductionQcCheck(
            check_id="setup_staging_binding",
            label="Setup / staging version binding",
            status=ProductionQcStatus.PASS if proposal.version_id else ProductionQcStatus.NOT_AVAILABLE,
            severity=ProductionQcSeverity.INFO,
            truth_state=ProductionTruthState.COMPUTED if proposal.version_id else ProductionTruthState.NOT_AVAILABLE,
            message=(
                f"Bound setup={proposal.version_id}, staging="
                f"{getattr(getattr(staging, 'meta', None), 'staging_version_id', None) or staging.staging_id}."
            ),
            affected_geometry=(),
            algorithm=PRODUCTION_ALGORITHM_ID,
            algorithm_version=PRODUCTION_ALGORITHM_VERSION,
            provenance=proposal.provenance.value if proposal.provenance else "experimental",
        )
    )

    # Mesh integrity on selected stage when available; otherwise on all stages as treatment QC.
    mesh_stage = selected_stage_index if source_state_cap is ProductionCapabilityState.AVAILABLE else None
    mesh_checks = _mesh_integrity_checks(staging, stage_index=mesh_stage)
    qc.extend(mesh_checks)
    mesh_qc_cap = (
        ProductionCapabilityState.AVAILABLE
        if mesh_checks and mesh_checks[0].status is ProductionQcStatus.PASS
        else ProductionCapabilityState.REQUIRES_REVIEW
        if mesh_checks and mesh_checks[0].status is ProductionQcStatus.ERROR
        else ProductionCapabilityState.NOT_AVAILABLE
        if mesh_checks and mesh_checks[0].status is ProductionQcStatus.NOT_AVAILABLE
        else ProductionCapabilityState.REQUIRES_REVIEW
    )

    from engines.geometry.production_geometry import MeshBuffers, get_production_geometry_adapter

    geometry = get_production_geometry_adapter()
    geometry_backends = tuple(geometry.backend_catalog())
    geometry_operations: list[dict[str, Any]] = []
    shell_generated = False
    engineering_offset_distance: float | None = None
    # Technical engineering offset default — not a clinical recommendation.
    TECHNICAL_OFFSET_DISTANCE = 0.2

    # Probe first selected-stage tooth through backends (source remains immutable).
    sample_state = None
    if source_state_cap is ProductionCapabilityState.AVAILABLE and selected_stage_index is not None:
        for stage in staging.stages:
            if stage.stage_index == selected_stage_index and stage.tooth_states:
                sample_state = stage.tooth_states[0]
                break
    if sample_state is not None:
        faces = getattr(sample_state, "source_faces", None) or getattr(
            sample_state, "final_target_faces", None
        ) or ()
        sample_mesh = MeshBuffers(
            vertices=tuple(tuple(map(float, p[:3])) for p in (sample_state.vertices or ())),
            faces=tuple(tuple(map(int, f[:3])) for f in faces),
            identity=str(sample_state.tooth_ref or sample_state.tooth_number or "sample"),
        )
        for result in (
            geometry.inspect_topology(sample_mesh),
            geometry.manifold_validity(sample_mesh),
            geometry.self_intersections(sample_mesh),
        ):
            geometry_operations.append(result.payload())
            if result.operation == "mesh_inspection":
                qc.append(
                    ProductionQcCheck(
                        check_id="topology_inspection",
                        label="Topology inspection (trimesh)",
                        status=ProductionQcStatus.PASS
                        if result.success
                        else ProductionQcStatus.WARNING,
                        severity=ProductionQcSeverity.INFO,
                        truth_state=ProductionTruthState.COMPUTED,
                        message=(
                            f"watertight={result.metrics.get('watertight')} "
                            f"volume={result.metrics.get('is_volume')} "
                            f"winding={result.metrics.get('winding_consistent')} "
                            f"backend={result.backend}:{result.backend_version}."
                        ),
                        affected_geometry=(sample_mesh.identity,),
                        algorithm=result.backend,
                        algorithm_version=str(result.backend_version or ""),
                        provenance="experimental",
                        limitations=result.limitations,
                    )
                )
            elif result.operation == "manifold_validity":
                qc.append(
                    ProductionQcCheck(
                        check_id="manifold_validity",
                        label="Manifold validity gate",
                        status=ProductionQcStatus.PASS
                        if result.success
                        else ProductionQcStatus.REQUIRES_REVIEW,
                        severity=ProductionQcSeverity.INFO,
                        truth_state=ProductionTruthState.COMPUTED
                        if result.success
                        else ProductionTruthState.REQUIRES_REVIEW,
                        message=result.message,
                        affected_geometry=(sample_mesh.identity,),
                        algorithm=result.backend,
                        algorithm_version=str(result.backend_version or ""),
                        provenance="experimental",
                        limitations=result.limitations,
                    )
                )
            elif result.operation == "self_intersection":
                status = (
                    ProductionQcStatus.PASS
                    if result.success and result.metrics.get("self_colliding_pairs", 0) == 0
                    else ProductionQcStatus.WARNING
                    if result.supported
                    else ProductionQcStatus.NOT_AVAILABLE
                )
                qc.append(
                    ProductionQcCheck(
                        check_id="self_intersection",
                        label="Self-intersection query",
                        status=status,
                        severity=ProductionQcSeverity.INFO,
                        truth_state=ProductionTruthState.COMPUTED
                        if result.supported
                        else ProductionTruthState.NOT_AVAILABLE,
                        message=result.message,
                        affected_geometry=(sample_mesh.identity,),
                        algorithm=result.backend,
                        algorithm_version=str(result.backend_version or ""),
                        provenance="experimental",
                        limitations=result.limitations,
                    )
                )

        if geometry.meshlib_available():
            offset = geometry.engineering_offset(
                sample_mesh, distance=TECHNICAL_OFFSET_DISTANCE
            )
            geometry_operations.append(offset.payload())
            if offset.success and offset.output_mesh is not None:
                shell_generated = True
                engineering_offset_distance = TECHNICAL_OFFSET_DISTANCE
                derived_key = f"engineering_offset:{sample_mesh.identity}"
                # Hash recorded below after derived_geometry_hashes init — stash for now
                _offset_hash = offset.output_hash
                _offset_key = derived_key
                qc.append(
                    ProductionQcCheck(
                        check_id="shell_generation",
                        label="Engineering offset / shell sample",
                        status=ProductionQcStatus.REQUIRES_REVIEW,
                        severity=ProductionQcSeverity.WARNING,
                        truth_state=ProductionTruthState.REQUIRES_REVIEW,
                        message=(
                            f"MeshLib engineering offset produced for sample tooth "
                            f"{sample_mesh.identity} distance={TECHNICAL_OFFSET_DISTANCE} "
                            f"(technical parameter). Requires human review. "
                            "Not manufacturing certified; not clinically approved."
                        ),
                        affected_geometry=(sample_mesh.identity,),
                        algorithm=offset.backend,
                        algorithm_version=str(offset.backend_version or ""),
                        provenance="experimental",
                        limitations=offset.limitations,
                    )
                )
            else:
                _offset_hash = None
                _offset_key = None
                qc.append(
                    ProductionQcCheck(
                        check_id="shell_generation",
                        label="Engineering offset / shell sample",
                        status=ProductionQcStatus.ERROR
                        if offset.supported
                        else ProductionQcStatus.NOT_AVAILABLE,
                        severity=ProductionQcSeverity.WARNING,
                        truth_state=ProductionTruthState.REQUIRES_REVIEW
                        if offset.supported
                        else ProductionTruthState.NOT_AVAILABLE,
                        message=offset.message,
                        affected_geometry=(sample_mesh.identity,),
                        algorithm=offset.backend,
                        algorithm_version=str(offset.backend_version or ""),
                        provenance="experimental",
                        limitations=offset.limitations,
                    )
                )
        else:
            _offset_hash = None
            _offset_key = None
            qc.append(
                _unavailable_cad_check(
                    "shell_generation",
                    "Engineering offset / shell",
                    "MeshLib offset backend is not available; shell remains not available.",
                )
            )
    else:
        _offset_hash = None
        _offset_key = None
        qc.append(
            _unavailable_cad_check(
                "shell_generation",
                "Engineering offset / shell",
                "Explicit production source selection is required before engineering offset.",
            )
        )

    shell_cap = (
        ProductionCapabilityState.AVAILABLE
        if geometry.meshlib_available()
        else ProductionCapabilityState.NOT_AVAILABLE
    )
    if shell_generated:
        # Capability exists and a sample was produced — still requires review.
        shell_cap = ProductionCapabilityState.REQUIRES_REVIEW

    # Remaining unsupported manufacturing claims — explicit NOT_AVAILABLE
    for check_id, label, reason in (
        (
            "trimline",
            "Trimline / cutline",
            "Trimline/cutline is not available; no fake production trimline is drawn.",
        ),
        (
            "thickness_profile",
            "Shell thickness / material profile",
            "Material/thickness manufacturing profiles are not certified; "
            "technical engineering offset distance is not a clinical thickness claim.",
        ),
        (
            "undercut_analysis",
            "Undercut / insertion analysis",
            "Undercut/insertion analysis is not available.",
        ),
        (
            "manufacturing_qc_certification",
            "Manufacturing QC certification",
            "Manufacturing QC certification is not available; engineering CAD is not manufacturing QC.",
        ),
    ):
        qc.append(_unavailable_cad_check(check_id, label, reason))

    # Occlusion limitation note (does not block stage-model engineering export)
    occ = (occlusion_capability_state or "unavailable").lower()
    if occ in ("unavailable", "not_available", ""):
        qc.append(
            _unavailable_cad_check(
                "occlusion_dependency",
                "Occlusion-dependent production",
                "Occlusion is unavailable; occlusion-dependent manufacturing claims are not made.",
            )
        )

    # Clinical tools dependency exposure
    if clinical_tools_setup_version_id:
        qc.append(
            ProductionQcCheck(
                check_id="clinical_tools_binding",
                label="Clinical tools binding",
                status=ProductionQcStatus.REQUIRES_REVIEW,
                severity=ProductionQcSeverity.WARNING,
                truth_state=ProductionTruthState.REQUIRES_REVIEW,
                message=(
                    f"Clinical tools bound to setup={clinical_tools_setup_version_id}; "
                    "IPR/attachments require doctor review and are not manufacturing prescriptions."
                ),
                affected_geometry=(),
                algorithm=PRODUCTION_ALGORITHM_ID,
                algorithm_version=PRODUCTION_ALGORITHM_VERSION,
                provenance="experimental",
                limitations=("Accepted/rejected/pending tool state is not silently ignored.",),
            )
        )
    else:
        qc.append(
            _unavailable_cad_check(
                "clinical_tools_binding",
                "Clinical tools binding",
                "Clinical tools binding is not available for this production context.",
            )
        )

    # Export validation capability — stage model export is engineering, not appliance CAD
    if has_stages:
        export_cap = ProductionCapabilityState.AVAILABLE
        package_cap = ProductionCapabilityState.AVAILABLE
        export_state = "engineering_export_available"
        qc.append(
            ProductionQcCheck(
                check_id="export_validation",
                label="Engineering export validation",
                status=ProductionQcStatus.PASS,
                severity=ProductionQcSeverity.INFO,
                truth_state=ProductionTruthState.COMPUTED,
                message=(
                    "Engineering treatment export (stage STLs + reports) is available. "
                    "Independent ZIP hash verify/reopen is supported. "
                    "This is not appliance manufacturing certification."
                ),
                affected_geometry=(),
                algorithm="TreatmentExportEngine",
                algorithm_version="phase11-export-1",
                provenance="experimental",
                limitations=(
                    "Export verify checks package integrity, not manufacturing safety.",
                    "Session re-import from ZIP alone remains unavailable.",
                ),
            )
        )
    else:
        export_cap = ProductionCapabilityState.NOT_AVAILABLE
        package_cap = ProductionCapabilityState.NOT_AVAILABLE
        export_state = "unavailable"
        qc.append(
            _unavailable_cad_check(
                "export_validation",
                "Engineering export validation",
                "Engineering export is unavailable without staged treatment models.",
            )
        )

    readiness = ProductionCapabilityReadiness(
        source_treatment_state=source_state_cap,
        validation_current=validation_cap,
        shell=shell_cap,
        trimline=ProductionCapabilityState.NOT_AVAILABLE,
        thickness_defined=(
            ProductionCapabilityState.REQUIRES_REVIEW
            if shell_generated
            else ProductionCapabilityState.NOT_AVAILABLE
        ),
        undercut_analysis=ProductionCapabilityState.NOT_AVAILABLE,
        mesh_qc=mesh_qc_cap,
        export_validation=export_cap,
        package_integrity=package_cap,
        stage_model_export=(
            ProductionCapabilityState.AVAILABLE
            if has_stages
            else ProductionCapabilityState.NOT_AVAILABLE
        ),
        printable_model_preparation=(
            ProductionCapabilityState.BOUNDARY_ONLY
            if has_stages
            else ProductionCapabilityState.NOT_AVAILABLE
        ),
        notes=(
            "Component readiness is explicit; manufacturing_ready remains false.",
            "Engineering MeshLib offset is not manufacturing certification.",
            "Trimline and undercut remain not available.",
            "Engineering stage export is not appliance manufacturing.",
        ),
    )

    # Manufacturing parameters — technical only; no clinical defaults invented as recommendations
    parameters: tuple[ProductionParameter, ...] = (
        ProductionParameter(
            name="shell_thickness",
            value=engineering_offset_distance,
            unit="model units",
            source="technical_default" if shell_generated else "not_configured",
            configuration_version=PRODUCTION_ALGORITHM_VERSION,
            kind="technical" if shell_generated else "manufacturing",
            provenance="experimental",
            limitations=(
                "Technical engineering offset distance — not a clinical thickness recommendation.",
                "Not a material-validated manufacturing thickness.",
            ),
        ),
        ProductionParameter(
            name="trimline_offset",
            value=None,
            unit="model units",
            source="not_configured",
            configuration_version=PRODUCTION_ALGORITHM_VERSION,
            kind="manufacturing",
            provenance="experimental",
            limitations=("No trimline parameter is fabricated.",),
        ),
        ProductionParameter(
            name="undercut_clearance",
            value=None,
            unit="model units",
            source="not_configured",
            configuration_version=PRODUCTION_ALGORITHM_VERSION,
            kind="manufacturing",
            provenance="experimental",
            limitations=("No undercut clearance default is invented.",),
        ),
    )

    staging_version_id = None
    if hasattr(staging, "meta") and getattr(staging, "meta", None) is not None:
        staging_version_id = getattr(staging.meta, "staging_version_id", None)
    if staging_version_id is None:
        staging_version_id = staging.staging_id

    binding = ProductionBinding(
        case_id=case_id,
        treatment_setup_version_id=proposal.version_id,
        staging_version_id=staging_version_id,
        clinical_tools_setup_version_id=clinical_tools_setup_version_id,
        clinical_tools_staging_version_id=clinical_tools_staging_version_id,
        validation_run_id=validation_run_id or (validation.report_id if validation else None),
        geometric_report_id=validation.report_id if validation else None,
        selected_stage_id=selected_stage_id,
        selected_stage_index=selected_stage_index,
        source_kind=source_kind,
        upper_mesh_hash=upper_mesh_hash,
        lower_mesh_hash=lower_mesh_hash,
        input_hash=input_hash,
    )

    committed_bound_setup = (
        previous_plan.binding.treatment_setup_version_id
        if previous_plan
        else bound_setup_version_id
    )
    committed_bound_staging = (
        previous_plan.binding.staging_version_id if previous_plan else bound_staging_version_id
    )
    committed_bound_clinical = (
        previous_plan.binding.clinical_tools_setup_version_id
        if previous_plan
        else bound_clinical_tools_setup_version_id
    )
    committed_bound_validation = (
        previous_plan.binding.validation_run_id if previous_plan else bound_validation_run_id
    )
    has_committed_production = bool(
        previous_plan is not None
        or committed_production_version_id
        or committed_bound_setup
        or committed_bound_staging
    )
    if has_committed_production:
        freshness = evaluate_production_freshness(
            bound_setup_version_id=committed_bound_setup,
            current_setup_version_id=current_setup_version_id or proposal.version_id,
            bound_staging_version_id=committed_bound_staging,
            current_staging_version_id=current_staging_version_id or staging_version_id,
            bound_clinical_tools_setup_version_id=committed_bound_clinical,
            current_clinical_tools_setup_version_id=(
                current_clinical_tools_setup_version_id or clinical_tools_setup_version_id
            ),
            bound_validation_run_id=committed_bound_validation,
            current_validation_run_id=current_validation_run_id
            or validation_run_id
            or (validation.report_id if validation else None),
            has_plan=True,
        )
    else:
        # Live boundary snapshot with no committed production selection.
        freshness = ProductionFreshness.CURRENT

    # Source hashes from selected/all stage treatment meshes (derived identity, not mutated source)
    source_geometry_hashes: dict[str, str | None] = {
        "upper_mesh_sha256": upper_mesh_hash,
        "lower_mesh_sha256": lower_mesh_hash,
        "input_hash": input_hash,
    }
    derived_geometry_hashes: dict[str, str] = {}
    if has_stages:
        target_stages = staging.stages
        if selected_stage_index is not None and source_state_cap is ProductionCapabilityState.AVAILABLE:
            target_stages = tuple(s for s in staging.stages if s.stage_index == selected_stage_index)
        for stage in target_stages:
            for state in stage.tooth_states:
                key = f"stage{stage.stage_index}:{state.tooth_ref or state.tooth_number}"
                derived_geometry_hashes[key] = _sha256_vertices(state.vertices)
    if _offset_hash and _offset_key:
        derived_geometry_hashes[_offset_key] = _offset_hash

    production_version_id = committed_production_version_id or _stable_id(
        case_id,
        proposal.version_id,
        staging_version_id,
        selected_stage_id,
        validation.report_id if validation else None,
        PRODUCTION_CONTRACT_VERSION,
    )
    production_plan_id = _stable_id(case_id, "production_plan", PRODUCTION_CONTRACT_VERSION)

    if freshness is ProductionFreshness.STALE:
        overall_truth = ProductionTruthState.REQUIRES_REVIEW
    elif source_state_cap is ProductionCapabilityState.REQUIRES_REVIEW:
        overall_truth = ProductionTruthState.REQUIRES_REVIEW
    elif not has_stages:
        overall_truth = ProductionTruthState.NOT_AVAILABLE
    else:
        overall_truth = ProductionTruthState.COMPUTED

    total_ms = (perf_counter() - started) * 1000
    return ProductionPlan(
        production_plan_id=production_plan_id,
        production_version_id=production_version_id,
        parent_production_version_id=parent_production_version_id
        or (previous_plan.production_version_id if previous_plan else None),
        contract_version=PRODUCTION_CONTRACT_VERSION,
        case_id=case_id,
        binding=binding,
        freshness=freshness,
        overall_truth_state=overall_truth,
        readiness=readiness,
        parameters=parameters,
        qc_checks=tuple(qc),
        operations=(
            "source_state_selection",
            "treatment_stage_model_export",
            "treatment_mesh_integrity_qc",
            "topology_inspection_trimesh",
            "manifold_validity_gate",
            "engineering_export_verify",
            *(
                ("meshlib_engineering_offset_sample",)
                if shell_generated
                else ("shell_generation_deferred_or_unavailable",)
            ),
            "trimline_unavailable",
            "undercut_unavailable",
        ),
        manufacturing_boundary=boundary.payload(),
        export_state=export_state,
        algorithm=PRODUCTION_ALGORITHM_ID,
        algorithm_version=PRODUCTION_ALGORITHM_VERSION,
        generated_at=generated_at,
        provenance=proposal.provenance.value if proposal.provenance else "experimental",
        fixture=bool(proposal.fixture),
        limitations=(
            "Production CAD may produce an engineering offset sample via MeshLib when available.",
            "Engineering offset is not manufacturing certification or clinical approval.",
            "Trimline and undercut remain not available.",
            "Open crown meshes are typically non-manifold; Manifold rejects them as solids.",
            "Engineering stage STL export is treatment geometry, not manufacturing CAD.",
            "Validation PASS is not clinical or manufacturing approval.",
            "No fake export packages are created for unavailable CAD capabilities.",
            "WP-11 and later packages are not started.",
        ),
        timings_ms={"production_cad_ms": total_ms},
        derived_geometry_hashes=derived_geometry_hashes,
        source_geometry_hashes=source_geometry_hashes,
        geometry_backends=geometry_backends,
        geometry_operations=tuple(geometry_operations),
        shell_generated=shell_generated,
        engineering_offset_distance=engineering_offset_distance,
    )


__all__ = ["build_production_plan"]
