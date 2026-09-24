"""P0.3: export integrity must use semantic tooth_ref when FDI is unavailable."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from domain.case.provenance import DataProvenance
from domain.tooth.identification import (
    ArchType,
    IdentificationConfidence,
    IdentificationStatus,
    IdentifiedTooth,
    ToothCoordinateSystem,
    ToothIdentificationResult,
)
from domain.tooth.segmentation import ToothInstance
from domain.treatment_plan.input import TreatmentPlanningInput, TreatmentPlanningMode
from domain.treatment_plan.setup import ToothMovement, TreatmentObjective, TreatmentObjectiveType
from domain.treatment_plan.staging import StagingConfiguration
from engines.export import TreatmentExportEngine, TreatmentExportError
from engines.export.treatment_export import _tooth_identity_key
from engines.planning.proposals import TreatmentProposalEngine
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.staging_engine import TreatmentStagingEngine
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)


def _semantic_tooth(instance_id: int, origin: tuple[float, float, float]) -> IdentifiedTooth:
    ox, oy, oz = origin
    vertices = (
        (ox, oy, oz),
        (ox + 1.0, oy, oz),
        (ox, oy + 1.0, oz),
        (ox, oy, oz + 1.0),
    )
    faces = ((0, 1, 2), (0, 2, 3), (0, 3, 1), (1, 3, 2))
    centroid = (ox + 0.25, oy + 0.25, oz + 0.25)
    instance = ToothInstance(
        instance_id=instance_id,
        triangle_indices=(0, 1, 2, 3),
        vertex_indices=(0, 1, 2, 3),
        mesh_vertices=vertices,
        mesh_faces=faces,
        centroid=centroid,
        confidence=0.0,
        provenance=DataProvenance.EXPERIMENTAL,
        fixture=True,
        tooth_ref=f"upper:instance:{instance_id}",
        semantic_label=11 + instance_id,
        arch="upper",
    )
    return IdentifiedTooth(
        instance=instance,
        identity=None,
        landmarks=None,
        coordinate_system=ToothCoordinateSystem(
            origin=centroid,
            lateral_axis=(1.0, 0.0, 0.0),
            anterior_axis=(0.0, 1.0, 0.0),
            vertical_axis=(0.0, 0.0, 1.0),
        ),
        confidence=IdentificationConfidence(
            0.0, IdentificationStatus.UNCERTAIN, ("semantic-only",)
        ),
        provenance=DataProvenance.EXPERIMENTAL,
        fixture=True,
        tooth_ref=instance.tooth_ref,
        semantic_label=instance.semantic_label,
        planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL.value,
    )


def semantic_export_inputs():
    identification = ToothIdentificationResult(
        arch=ArchType.UPPER,
        teeth=(
            _semantic_tooth(0, (0.0, 0.0, 0.0)),
            _semantic_tooth(1, (3.0, 0.0, 0.0)),
        ),
        provenance=DataProvenance.EXPERIMENTAL,
        fixture=True,
        notes="p0-3-semantic-export",
    )
    treatment_input = TreatmentPlanningInput.from_identification(
        identification, planning_mode=TreatmentPlanningMode.SEMANTIC_ONLY_EXPERIMENTAL
    )
    objectives = (
        TreatmentObjective(
            "p0-3",
            TreatmentObjectiveType.ALIGNMENT,
            "semantic export integrity",
            (("upper:instance:0", ToothMovement(translation_x=0.2)),),
        ),
    )
    plan = TreatmentPlanningEngine().generate_from_input(
        "p0-3-semantic-export", treatment_input, objectives
    )
    assert plan.setup is not None
    assert all(state.tooth_number is None for state in plan.setup.source_states)
    assert all(state.tooth_ref for state in plan.setup.source_states)
    staging = TreatmentStagingEngine().generate(plan, StagingConfiguration(stage_count=3))
    validation = GeometricValidationEngine().validate(
        staging, GeometricValidationConfiguration(1.0, 0.001, 0.0)
    )
    proposals = TreatmentProposalEngine().generate(plan)
    return plan, staging, validation, proposals


def test_tooth_identity_key_prefers_fdi_then_tooth_ref() -> None:
    class State:
        def __init__(self, tooth_number=None, tooth_ref=None):
            self.tooth_number = tooth_number
            self.tooth_ref = tooth_ref

    assert _tooth_identity_key(State(tooth_number=11, tooth_ref="upper:instance:0")) == 11
    assert _tooth_identity_key(State(tooth_ref="lower:instance:3")) == "lower:instance:3"
    with pytest.raises(TreatmentExportError, match="missing both"):
        _tooth_identity_key(State())


def test_semantic_only_export_passes_source_and_final_geometry_checks(tmp_path) -> None:
    plan, staging, validation, proposals = semantic_export_inputs()
    package = TreatmentExportEngine().export(
        tmp_path / "semantic-export",
        plan,
        staging,
        validation,
        proposals,
        export_timestamp="2026-09-24T00:00:00+00:00",
    )
    assert package.incomplete is False
    manifest = json.loads(package.manifest_path.read_text())
    assert manifest["clinical_approval"] is False
    assert "tooth None" not in json.dumps(manifest)
    assert not any("tooth None" in warning for warning in manifest.get("warnings", []))

    source_by_ref = {state.tooth_ref: state for state in plan.setup.source_states}
    target_by_ref = {state.tooth_ref: state for state in plan.setup.target_states}
    for state in staging.stages[0].tooth_states:
        assert state.tooth_number is None
        assert state.vertices == source_by_ref[state.tooth_ref].source_vertices
    for state in staging.final_stage.tooth_states:
        assert state.tooth_number is None
        assert state.vertices == target_by_ref[state.tooth_ref].target_vertices

    movements = json.loads((package.root / "reports/movements.json").read_text())["movements"]
    assert all(row["tooth_number"] is None for row in movements)
    assert {row["tooth_ref"] for row in movements} >= {
        "upper:instance:0",
        "upper:instance:1",
    }
    assert all(row["tooth_key"] == row["tooth_ref"] for row in movements)


def test_semantic_export_rehash_matches_manifest_and_zip(tmp_path) -> None:
    plan, staging, validation, proposals = semantic_export_inputs()
    package = TreatmentExportEngine().export(
        tmp_path / "semantic-rehash",
        plan,
        staging,
        validation,
        proposals,
        export_timestamp="fixed-ts",
    )
    manifest = json.loads(package.manifest_path.read_text())
    for artifact in manifest["files"]:
        digest = hashlib.sha256((package.root / artifact["path"]).read_bytes()).hexdigest()
        assert digest == artifact["sha256"]
    with zipfile.ZipFile(package.zip_path) as archive:
        assert "manifest.json" in archive.namelist()
        assert set(archive.namelist()) == set(package.files)
        zipped_manifest = json.loads(archive.read("manifest.json"))
        assert zipped_manifest["manifest_hash"] == package.manifest_hash
        for artifact in zipped_manifest["files"]:
            assert (
                hashlib.sha256(archive.read(artifact["path"])).hexdigest() == artifact["sha256"]
            )


def test_semantic_export_still_detects_true_geometry_mismatch(tmp_path) -> None:
    plan, staging, validation, proposals = semantic_export_inputs()
    from dataclasses import replace

    broken_first = replace(
        staging.stages[0],
        tooth_states=tuple(
            replace(
                state,
                vertices=tuple((v[0] + 9.0, v[1], v[2]) for v in state.vertices),
            )
            if state.tooth_ref == "upper:instance:0"
            else state
            for state in staging.stages[0].tooth_states
        ),
    )
    broken_staging = replace(staging, stages=(broken_first, *staging.stages[1:]))
    with pytest.raises(TreatmentExportError, match="Stage 0 differs from source geometry"):
        TreatmentExportEngine().export(
            tmp_path / "broken", plan, broken_staging, validation, proposals
        )
    with pytest.raises(TreatmentExportError) as raised:
        TreatmentExportEngine().export(
            tmp_path / "broken2", plan, broken_staging, validation, proposals
        )
    assert "tooth None" not in str(raised.value)
    assert "upper:instance:0" in str(raised.value)
