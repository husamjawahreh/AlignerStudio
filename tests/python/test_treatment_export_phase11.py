import hashlib
import json
import zipfile
from dataclasses import replace

import pytest

from domain.tooth.identification import ArchType
from domain.treatment_plan.staging import StagingConfiguration
from engines.arrangement.identification import ToothIdentificationEngine
from engines.export import TreatmentExportEngine, TreatmentExportError
from engines.planning.proposals import TreatmentProposalEngine
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.staging_engine import TreatmentStagingEngine
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)
from tests.fixtures.synthetic_arch import build_synthetic_arch
from tests.fixtures.synthetic_objectives import mild_crowding_objective, rotation_objective


def export_inputs():
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    plan = TreatmentPlanningEngine().generate(
        "fixture-export-case", identification, (mild_crowding_objective(), rotation_objective())
    )
    staging = TreatmentStagingEngine().generate(plan, StagingConfiguration(stage_count=3))
    validation = GeometricValidationEngine().validate(
        staging, GeometricValidationConfiguration(1.0, 0.001, 0.0)
    )
    proposals = TreatmentProposalEngine().generate(plan)
    return plan, staging, validation, proposals


def test_export_is_ordered_hashed_and_fixture_labeled(tmp_path) -> None:
    plan, staging, validation, proposals = export_inputs()
    package = TreatmentExportEngine().export(
        tmp_path / "export",
        plan,
        staging,
        validation,
        proposals,
        export_timestamp="2026-09-19T00:00:00+00:00",
    )
    manifest = json.loads(package.manifest_path.read_text())
    assert manifest["case_id"] == plan.case_id
    assert manifest["treatment_plan_id"] == plan.plan_id
    assert manifest["plan_version"] == plan.version_id
    assert manifest["staging_hash"] == staging.staging_id
    assert manifest["validation_hash"] == validation.report_id
    assert manifest["data_status"] == "fixture"
    assert manifest["fixture"] is True
    assert manifest["clinical_approval"] is False
    files = [entry["path"] for entry in manifest["files"]]
    assert files[:3] == [
        "reports/attachments.json",
        "reports/edit-history.json",
        "reports/ipr.json",
    ]
    assert [path for path in files if path.startswith("stages/")] == [
        "stages/stage-000.stl",
        "stages/stage-001.stl",
        "stages/stage-002.stl",
    ]
    for artifact in manifest["files"]:
        assert (
            hashlib.sha256((package.root / artifact["path"]).read_bytes()).hexdigest()
            == artifact["sha256"]
        )


def test_export_zip_contains_complete_package_and_is_deterministic_with_fixed_timestamp(
    tmp_path,
) -> None:
    plan, staging, validation, proposals = export_inputs()
    engine = TreatmentExportEngine()
    first = engine.export(
        tmp_path / "first", plan, staging, validation, proposals, export_timestamp="fixed"
    )
    second = engine.export(
        tmp_path / "second", plan, staging, validation, proposals, export_timestamp="fixed"
    )
    assert first.manifest_hash == second.manifest_hash
    assert first.zip_path.read_bytes() == second.zip_path.read_bytes()
    with zipfile.ZipFile(first.zip_path) as archive:
        assert archive.namelist() == list(first.files)
        assert "manifest.json" in archive.namelist()
        assert "reports/movements.csv" in archive.namelist()


def test_export_preserves_source_and_final_geometry_without_mutation(tmp_path) -> None:
    plan, staging, validation, proposals = export_inputs()
    source = plan.setup.source_states
    final = plan.setup.target_states
    package = TreatmentExportEngine().export(
        tmp_path / "export", plan, staging, validation, proposals
    )
    assert plan.setup.source_states == source
    assert plan.setup.target_states == final
    assert staging.stages[0].tooth_states[0].vertices == source[0].source_vertices
    assert staging.final_stage.tooth_states[0].vertices == final[0].target_vertices
    assert "solid stage-000-" in (package.root / "stages/stage-000.stl").read_text()
    assert "solid stage-002-" in (package.root / "stages/stage-002.stl").read_text()


def test_export_rejects_invalid_plan_version_and_can_mark_incomplete_package(tmp_path) -> None:
    plan, staging, validation, proposals = export_inputs()
    inconsistent = replace(proposals, version_id="wrong-version")
    engine = TreatmentExportEngine()
    with pytest.raises(TreatmentExportError, match="adjunct proposals"):
        engine.export(tmp_path / "strict", plan, staging, validation, inconsistent)
    package = engine.export(
        tmp_path / "incomplete", plan, staging, validation, inconsistent, allow_incomplete=True
    )
    manifest = json.loads(package.manifest_path.read_text())
    assert package.incomplete is True
    assert manifest["incomplete_engineering_export"] is True
    assert manifest["warnings"]
