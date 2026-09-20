from dataclasses import replace

import pytest

from domain.tooth.identification import ArchType
from domain.treatment_plan.proposals import ProposalStatus
from engines.arrangement.identification import ToothIdentificationEngine
from engines.planning.proposals import TreatmentProposalEngine, TreatmentProposalError
from engines.planning.setup_engine import TreatmentPlanningEngine
from tests.fixtures.synthetic_arch import build_synthetic_arch
from tests.fixtures.synthetic_objectives import (
    mild_crowding_objective,
    rotation_objective,
    spacing_objective,
)


def build_plan():
    identification = ToothIdentificationEngine().identify(
        build_synthetic_arch(ArchType.UPPER), ArchType.UPPER
    )
    return TreatmentPlanningEngine().generate(
        "fixture-proposal-case",
        identification,
        (mild_crowding_objective(), spacing_objective(), rotation_objective()),
    )


def test_deterministic_ipr_and_attachment_proposals() -> None:
    engine = TreatmentProposalEngine()
    first = engine.generate(build_plan())
    second = engine.generate(build_plan())
    assert first == second
    assert first.proposal_id == second.proposal_id
    assert first.ipr.sites
    assert first.attachments.sites
    assert all(site.status is ProposalStatus.NEEDS_REVIEW for site in first.ipr.sites)
    assert all(site.status is ProposalStatus.NEEDS_REVIEW for site in first.attachments.sites)
    assert first.fixture is True
    assert first.provenance.value == "generated"


def test_ipr_and_attachment_warning_states_are_explicit() -> None:
    result = TreatmentProposalEngine().generate(build_plan())
    assert all(site.warnings for site in result.ipr.sites)
    assert all(site.warnings for site in result.attachments.sites)
    assert all(site.dimensions is None for site in result.attachments.sites)


def test_lifecycle_modify_accept_reject_and_reset() -> None:
    engine = TreatmentProposalEngine()
    generated = engine.generate(build_plan())
    site = generated.ipr.sites[0]
    modified = engine.modify_ipr(generated, site.site_id, 0.1)
    assert modified.ipr.sites[0].status is ProposalStatus.DOCTOR_MODIFIED
    accepted = engine.set_ipr_status(modified, site.site_id, ProposalStatus.ACCEPTED)
    assert accepted.ipr.sites[0].status is ProposalStatus.ACCEPTED
    rejected = engine.set_attachment_status(
        accepted, accepted.attachments.sites[0].site_id, ProposalStatus.REJECTED
    )
    assert rejected.attachments.sites[0].status is ProposalStatus.REJECTED
    assert engine.reset(generated) == generated


def test_invalid_site_and_invalid_amount_are_rejected() -> None:
    engine = TreatmentProposalEngine()
    generated = engine.generate(build_plan())
    with pytest.raises(TreatmentProposalError, match="Unknown IPR"):
        engine.modify_ipr(generated, "missing", 0.1)
    with pytest.raises(TreatmentProposalError, match="negative"):
        engine.modify_ipr(generated, generated.ipr.sites[0].site_id, -0.1)


def test_missing_setup_is_unable_to_determine() -> None:
    plan = replace(build_plan(), setup=None)
    result = TreatmentProposalEngine().generate(plan)
    assert result.ipr.status is ProposalStatus.UNABLE_TO_DETERMINE
    assert result.attachments.status is ProposalStatus.UNABLE_TO_DETERMINE
    assert result.warnings


def test_recalculated_plan_version_regenerates_proposal_ids_and_history() -> None:
    engine = TreatmentProposalEngine()
    original = engine.generate(build_plan())
    edited_plan = replace(build_plan(), plan_id="edited-plan", version_id="edited-version")
    regenerated = engine.generate(edited_plan, previous=original)
    assert regenerated.plan_id == edited_plan.plan_id
    assert regenerated.version_id == edited_plan.version_id
    assert regenerated.proposal_id != original.proposal_id
    assert original.proposal_id in regenerated.history
    assert regenerated.ipr.plan_id == edited_plan.plan_id
    assert regenerated.attachments.plan_id == edited_plan.plan_id
