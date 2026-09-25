"""P5 — Validation review summary, manufacturing boundary, export verify, proposal audit."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from app.main import app
from app.store import case_store
from app.treatment_sessions import treatment_sessions
from domain.tooth.identification import ArchType
from domain.treatment_plan.manufacturing import (
    ArtifactLayer,
    ManufacturingCapabilityStatus,
    build_manufacturing_boundary_report,
)
from domain.treatment_plan.proposals import ProposalStatus
from domain.treatment_plan.staging import StagingConfiguration
from engines.arrangement.identification import ToothIdentificationEngine
from engines.export import TreatmentExportEngine
from engines.planning.proposals import TreatmentProposalEngine
from engines.planning.setup_engine import TreatmentPlanningEngine
from engines.planning.staging_engine import TreatmentStagingEngine
from engines.validation.geometric_engine import (
    GeometricValidationConfiguration,
    GeometricValidationEngine,
)
from engines.validation.review_summary import build_validation_review_summary
from fastapi.testclient import TestClient
from tests.fixtures.synthetic_arch import build_synthetic_arch
from tests.fixtures.synthetic_objectives import mild_crowding_objective, rotation_objective

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_store():
    case_store.clear()
    treatment_sessions.clear()
    yield
    case_store.clear()
    treatment_sessions.clear()


def _treatment_stack():
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    plan = TreatmentPlanningEngine().generate(
        "fixture-p5-case", identification, (mild_crowding_objective(), rotation_objective())
    )
    staging = TreatmentStagingEngine().generate(plan, StagingConfiguration(stage_count=3))
    validation = GeometricValidationEngine().validate(
        staging, GeometricValidationConfiguration(1.0, 0.001, 0.0)
    )
    proposals = TreatmentProposalEngine().generate(plan)
    return plan, staging, validation, proposals


def test_validation_review_summary_is_truthful_and_includes_provenance() -> None:
    plan, staging, validation, _ = _treatment_stack()
    summary = build_validation_review_summary(plan, staging, validation)
    payload = summary.payload()
    assert payload["geometry"] == "computed"
    assert payload["contacts"] == "computed"
    assert payload["proximity"] == "computed"
    assert payload["collisions"] == "computed"
    assert payload["stageConsistency"] == "computed"
    assert payload["provenance"] == "computed"
    assert payload["doctorReview"] == "required"
    assert payload["movementConstraints"] == "unavailable"
    assert any("movement limits" in finding.lower() for finding in payload["findings"])
    # Never invent artificial PASS — findings list retains engine warnings/errors.
    assert isinstance(payload["findings"], list)


def test_manufacturing_boundary_keeps_shells_unavailable() -> None:
    report = build_manufacturing_boundary_report(has_stage_models=True)
    payload = report.payload()
    assert payload["stageModelExport"] == ManufacturingCapabilityStatus.COMPUTED.value
    assert payload["applianceShellGeneration"] == ManufacturingCapabilityStatus.UNAVAILABLE.value
    assert payload["trimlineCutline"] == ManufacturingCapabilityStatus.UNAVAILABLE.value
    assert payload["manufacturingQcReport"] == ManufacturingCapabilityStatus.UNAVAILABLE.value
    assert payload["treatmentVsManufacturingSeparated"] is True
    assert ArtifactLayer.TREATMENT_DESIGN.value in payload["artifactLayers"]
    assert ArtifactLayer.MANUFACTURING_PREPARATION.value in payload["artifactLayers"]
    assert "no fake shells" in " ".join(payload["notes"]).lower()


def test_ipr_and_attachment_sites_are_auditable() -> None:
    plan, staging, _, proposals = _treatment_stack()
    final_stage = len(staging.stages) - 1
    assert proposals.ipr.sites
    site = proposals.ipr.sites[0]
    assert site.tooth_a is not None and site.tooth_b is not None
    assert site.current_measurement.value is not None
    assert site.target_measurement.value is not None
    assert site.proposed_amount is not None
    assert site.status == ProposalStatus.NEEDS_REVIEW
    assert site.stage_index is None  # assigned at review/export layer when unset

    modified = TreatmentProposalEngine().modify_ipr(proposals, site.site_id, 0.25)
    updated = next(item for item in modified.ipr.sites if item.site_id == site.site_id)
    assert updated.proposed_amount == 0.25
    assert updated.status == ProposalStatus.DOCTOR_MODIFIED

    accepted = TreatmentProposalEngine().set_ipr_status(
        modified, site.site_id, ProposalStatus.ACCEPTED
    )
    assert accepted.ipr.sites[0].status == ProposalStatus.ACCEPTED

    assert proposals.attachments.sites
    attachment = proposals.attachments.sites[0]
    assert attachment.dimensions is None
    assert attachment.generated is False
    assert attachment.attachment_type.value == "undetermined"
    assert attachment.reference_point is not None
    assert attachment.stage_index is None
    # Stage index is presentation-bound via review_bundle, not invented geometry.
    assert final_stage >= 0


def test_export_separates_manufacturing_and_verifies_hashes(tmp_path: Path) -> None:
    plan, staging, validation, proposals = _treatment_stack()
    engine = TreatmentExportEngine()
    package = engine.export(
        tmp_path / "export",
        plan,
        staging,
        validation,
        proposals,
        export_timestamp="2026-09-25T00:00:00+00:00",
    )
    manifest = json.loads(package.manifest_path.read_text())
    assert manifest["package_kind"] == "engineering_treatment_export"
    assert manifest["artifact_layers"]["treatment_design"] == "included"
    assert manifest["artifact_layers"]["geometric_validation"] == "included"
    assert manifest["artifact_layers"]["manufacturing_preparation"] == "unavailable"
    assert manifest["artifact_layers"]["manufacturing_validation"] == "unavailable"
    assert manifest["manufacturing_boundary"]["applianceShellGeneration"] == "unavailable"
    assert manifest["clinical_approval"] is False

    with zipfile.ZipFile(package.zip_path) as archive:
        names = archive.namelist()
    assert "manifest.json" in names
    assert any(name.startswith("stages/") for name in names)
    # No appliance shell / trimline artifacts invented.
    assert not any("shell" in name.lower() for name in names)
    assert not any("trimline" in name.lower() for name in names)

    verified = engine.verify_package(package.zip_path)
    assert verified["verified"] is True
    assert verified["manifest_hash_matches"] is True
    assert verified["missing_files"] == []
    assert verified["hash_mismatches"] == []
    assert verified["package_kind"] == "engineering_treatment_export"

    # Tamper detection: rewrite ZIP with mutated IPR report while keeping manifest hashes.
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(package.zip_path, "r") as source:
        with zipfile.ZipFile(tampered, "w") as destination:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == "reports/ipr.json":
                    data = b'{"tampered":true}'
                destination.writestr(info, data)
    broken = engine.verify_package(tampered)
    assert broken["verified"] is False
    assert "reports/ipr.json" in broken["hash_mismatches"]


def test_api_review_bundle_exposes_p5_fields_and_proposal_mutations() -> None:
    demo = client.post("/cases/demo")
    assert demo.status_code == 200
    case_id = demo.json()["case"]["id"]
    bundle = demo.json()["review_bundle"]

    summary = bundle["validationSummary"]
    assert summary["geometry"] == "computed"
    assert summary["provenance"] == "computed"
    assert summary["movementConstraints"] == "unavailable"
    assert summary["doctorReview"] == "required"
    assert summary["geometry"] != "pass"

    manufacturing = bundle["manufacturingBoundary"]
    assert manufacturing["applianceShellGeneration"] == "unavailable"
    assert manufacturing["treatmentVsManufacturingSeparated"] is True

    assert bundle["iprSites"]
    ipr = bundle["iprSites"][0]
    assert {"siteId", "toothA", "toothB", "currentDistance", "targetDistance", "proposedAmount", "stage", "status"} <= set(
        ipr
    )

    assert bundle["attachmentSites"]
    attachment = bundle["attachmentSites"][0]
    assert attachment["generated"] is False
    assert attachment["dimensions"] is None
    assert "stage" in attachment

    amount = client.patch(
        f"/cases/{case_id}/treatment/proposals/ipr/{ipr['siteId']}/amount",
        json={"amount": 0.33},
    )
    assert amount.status_code == 200
    updated_ipr = next(
        site for site in amount.json()["iprSites"] if site["siteId"] == ipr["siteId"]
    )
    assert updated_ipr["proposedAmount"] == 0.33
    assert updated_ipr["status"] == "doctor_modified"

    status = client.patch(
        f"/cases/{case_id}/treatment/proposals/ipr/{ipr['siteId']}/status",
        json={"status": "accepted"},
    )
    assert status.status_code == 200
    assert status.json()["iprSites"][0]["status"] == "accepted"

    attachment_status = client.patch(
        f"/cases/{case_id}/treatment/proposals/attachments/{attachment['siteId']}/status",
        json={"status": "rejected"},
    )
    assert attachment_status.status_code == 200
    assert attachment_status.json()["attachmentSites"][0]["status"] == "rejected"

    verified = client.post(f"/cases/{case_id}/export/verify")
    assert verified.status_code == 200
    body = verified.json()
    assert body["verified"] is True
    assert body["manufacturing_boundary"]["applianceShellGeneration"] == "unavailable"
