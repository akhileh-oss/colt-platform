"""Milestone 14's acceptance criterion, proven literally: "A campaign can be created,
validated, paused, resumed, and inspected without any external send" (CLAUDE.md §68).

Everything here is real: real Postgres, real RLS (via `SqlAlchemyCampaignRepository.create`),
and the real `CreateCampaign`/`ValidateCampaign`/`PauseCampaign`/`ResumeCampaign`/`GetCampaign`/
`ListCampaigns` use cases. No external send exists anywhere in this milestone — there is
nothing to mock. Every assertion re-reads the campaign back from Postgres through `GetCampaign`
rather than trusting the previous call's return value, so this proves persistence, not just
in-memory state.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from colt_application.errors import (
    CampaignValidationError,
    InvalidCampaignTransitionError,
    NotFoundError,
)
from colt_application.use_cases.create_campaign import CreateCampaign
from colt_application.use_cases.get_campaign import GetCampaign
from colt_application.use_cases.list_campaigns import ListCampaigns
from colt_application.use_cases.pause_campaign import PauseCampaign
from colt_application.use_cases.resume_campaign import ResumeCampaign
from colt_application.use_cases.validate_campaign import ValidateCampaign
from colt_db.repositories.campaign_repository import SqlAlchemyCampaignRepository
from colt_domain import CampaignStatus

NOW = datetime.now(UTC)


@pytest.mark.asyncio
async def test_a_campaign_can_be_created_validated_paused_resumed_and_inspected(
    open_app_session: Any, two_organizations: tuple[Any, Any]
) -> None:
    org_a, _ = two_organizations

    # Created.
    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        create_campaign = CreateCampaign(repo)
        campaign = await create_campaign(
            name="Q4 outbound",
            objective="Book 50 demos",
            icp_definition={"industry": "SaaS", "employee_count_min": 50},
            channels=["email", "linkedin"],
            schedule={"timezone": "UTC", "days": ["Mon", "Tue", "Wed", "Thu", "Fri"]},
            limits={"max_sends_per_day": 100},
        )
    assert campaign.status == CampaignStatus.DRAFT

    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        persisted = await GetCampaign(repo)(campaign.id)
    assert persisted.status == CampaignStatus.DRAFT
    assert persisted.name == "Q4 outbound"

    # An incomplete draft campaign is rejected and stays DRAFT.
    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        incomplete = await CreateCampaign(repo)(name="Incomplete draft")
    with pytest.raises(CampaignValidationError) as exc_info:
        session = await open_app_session()
        async with session, session.begin():
            repo = await SqlAlchemyCampaignRepository.create(session, org_a)
            await ValidateCampaign(repo)(incomplete.id, now=NOW)
    assert len(exc_info.value.issues) == 4
    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        still_draft = await GetCampaign(repo)(incomplete.id)
    assert still_draft.status == CampaignStatus.DRAFT

    # Validated: the fully-configured campaign activates.
    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        activated = await ValidateCampaign(repo)(campaign.id, now=NOW)
    assert activated.status == CampaignStatus.ACTIVE

    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        persisted = await GetCampaign(repo)(campaign.id)
    assert persisted.status == CampaignStatus.ACTIVE

    # Paused.
    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        paused = await PauseCampaign(repo)(campaign.id, now=NOW)
    assert paused.status == CampaignStatus.PAUSED

    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        persisted = await GetCampaign(repo)(campaign.id)
    assert persisted.status == CampaignStatus.PAUSED

    # A paused campaign cannot be paused again, and cannot be re-validated back to life.
    with pytest.raises(InvalidCampaignTransitionError):
        session = await open_app_session()
        async with session, session.begin():
            repo = await SqlAlchemyCampaignRepository.create(session, org_a)
            await PauseCampaign(repo)(campaign.id, now=NOW)
    with pytest.raises(InvalidCampaignTransitionError):
        session = await open_app_session()
        async with session, session.begin():
            repo = await SqlAlchemyCampaignRepository.create(session, org_a)
            await ValidateCampaign(repo)(campaign.id, now=NOW)

    # Resumed.
    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        resumed = await ResumeCampaign(repo)(campaign.id, now=NOW)
    assert resumed.status == CampaignStatus.ACTIVE

    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        persisted = await GetCampaign(repo)(campaign.id)
    assert persisted.status == CampaignStatus.ACTIVE

    # Inspected: both campaigns this organization created are listed.
    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        all_campaigns = await ListCampaigns(repo)()
    assert {c.id for c in all_campaigns} == {campaign.id, incomplete.id}


@pytest.mark.asyncio
async def test_getting_a_campaign_that_does_not_exist_raises_not_found(
    open_app_session: Any, two_organizations: tuple[Any, Any]
) -> None:
    org_a, _ = two_organizations
    from uuid import uuid4

    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyCampaignRepository.create(session, org_a)
        with pytest.raises(NotFoundError):
            await GetCampaign(repo)(uuid4())


@pytest.mark.asyncio
async def test_a_campaign_is_invisible_to_a_different_organization(
    open_app_session: Any, two_organizations: tuple[Any, Any]
) -> None:
    org_a, org_b = two_organizations

    session = await open_app_session()
    async with session, session.begin():
        repo_a = await SqlAlchemyCampaignRepository.create(session, org_a)
        campaign = await CreateCampaign(repo_a)(name="Org A's campaign")

    session = await open_app_session()
    async with session, session.begin():
        repo_b = await SqlAlchemyCampaignRepository.create(session, org_b)
        found = await repo_b.get(campaign.id)
        listed = await ListCampaigns(repo_b)()

    assert found is None
    assert listed == []
