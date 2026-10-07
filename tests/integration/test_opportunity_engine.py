"""Milestone 21's acceptance criterion, proven literally: "Positive conversations can become
auditable opportunities without duplicate creation" (CLAUDE.md §68).

**What this proves for real, against real Postgres:**

- Two separate positive-conversation triggers for the same company produce exactly one
  `Opportunity` row, never two — the literal "without duplicate creation" half, via
  `CreateOrUpdateOpportunity`'s dedup check (`get_open_by_company`).
- The opportunity pipeline state machine (`TransitionOpportunityStage`) moving a real row
  through its full lifecycle to `WON`, and rejecting an illegal jump, against real RLS-scoped
  Postgres.
- Owner assignment (`AssignOpportunityOwner`) persisting against a real `User` row.

**What this environment cannot prove, and why:**

`OpportunityAgent` itself constructs a real `AnthropicGateway` and calls it for real — no real
Anthropic API key exists in this environment (the same caveat carried since Milestone 08), so
no test here drives `evaluate_opportunity_activity` or the agent's own commercial-intent
judgment; `OpportunityAgent`'s own hermetic test
(`packages/python/colt-agents/tests/test_colt_agents_opportunity_agent.py`) proves that
mechanism without any real model call. This test proves the deterministic half the acceptance
criterion actually turns on: given a decision to create/update an opportunity (however it was
produced), does the right thing happen to the real `Opportunity` row.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from colt_application.errors import InvalidOpportunityTransitionError, NotFoundError
from colt_application.use_cases.assign_opportunity_owner import AssignOpportunityOwner
from colt_application.use_cases.create_or_update_opportunity import CreateOrUpdateOpportunity
from colt_application.use_cases.transition_opportunity_stage import TransitionOpportunityStage
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.opportunity_repository import SqlAlchemyOpportunityRepository
from colt_db.repositories.user_repository import SqlAlchemyUserRepository
from colt_domain import PipelineStage

SessionFactory = Any
NOW = datetime.now(UTC)


async def _seed_company(session: Any, org_id: UUID) -> UUID:
    companies = await SqlAlchemyCompanyRepository.create(session, org_id)
    company = await companies.add(name="Acme Rockets", domain="acme-rockets.example")
    return company.id


async def _seed_user(session: Any, org_id: UUID) -> UUID:
    """Users are provisioned through the auth flow, not an application-layer `CreateUser` use
    case — the same reasoning `test_policy_and_approval.py`'s own `_seed_user` already
    documents."""
    user_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO users (id, organization_id, external_auth_id, email, name, role) "
            "VALUES (:id, :org_id, :auth_id, :email, 'Rep', 'SALES')"
        ),
        {
            "id": user_id,
            "org_id": org_id,
            "auth_id": f"kc-sub-{user_id}",
            "email": f"rep-{user_id}@example.com",
        },
    )
    return user_id


@pytest.mark.asyncio
async def test_two_positive_conversations_for_the_same_company_never_create_a_duplicate(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        company_id = await _seed_company(seed_session, org_a)
        opportunities = await SqlAlchemyOpportunityRepository.create(seed_session, org_a)
        create_or_update = CreateOrUpdateOpportunity(opportunities)

        first = await create_or_update(company_id=company_id, source="conversation", now=NOW)
        second = await create_or_update(company_id=company_id, source="conversation", now=NOW)

        assert first.was_created is True
        assert second.was_created is False
        assert second.opportunity.id == first.opportunity.id

    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        opportunities_verify = await SqlAlchemyOpportunityRepository.create(verify_session, org_a)
        all_opportunities = await opportunities_verify.list_all()
        matching = [o for o in all_opportunities if o.company_id == company_id]
        assert len(matching) == 1


@pytest.mark.asyncio
async def test_an_opportunity_moves_through_the_full_pipeline_to_won(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        company_id = await _seed_company(seed_session, org_a)
        opportunities = await SqlAlchemyOpportunityRepository.create(seed_session, org_a)
        result = await CreateOrUpdateOpportunity(opportunities)(
            company_id=company_id, source="conversation", now=NOW
        )
        opportunity_id = result.opportunity.id

        transition = TransitionOpportunityStage(opportunities)
        for stage in (
            PipelineStage.DISCOVERY,
            PipelineStage.EVALUATION,
            PipelineStage.PROPOSAL,
            PipelineStage.NEGOTIATION,
            PipelineStage.WON,
        ):
            await transition(opportunity_id, stage, now=NOW)

    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        opportunities_verify = await SqlAlchemyOpportunityRepository.create(verify_session, org_a)
        reread = await opportunities_verify.get(opportunity_id)
        assert reread is not None
        assert reread.pipeline_stage == PipelineStage.WON


@pytest.mark.asyncio
async def test_an_illegal_transition_is_rejected_and_the_stage_is_unchanged(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        company_id = await _seed_company(seed_session, org_a)
        opportunities = await SqlAlchemyOpportunityRepository.create(seed_session, org_a)
        result = await CreateOrUpdateOpportunity(opportunities)(
            company_id=company_id, source="conversation", now=NOW
        )
        opportunity_id = result.opportunity.id

        transition = TransitionOpportunityStage(opportunities)
        with pytest.raises(InvalidOpportunityTransitionError):
            await transition(opportunity_id, PipelineStage.WON, now=NOW)

    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        opportunities_verify = await SqlAlchemyOpportunityRepository.create(verify_session, org_a)
        reread = await opportunities_verify.get(opportunity_id)
        assert reread is not None
        assert reread.pipeline_stage == PipelineStage.QUALIFIED


@pytest.mark.asyncio
async def test_assigning_an_unknown_owner_raises_and_an_assign_persists(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        company_id = await _seed_company(seed_session, org_a)
        owner_id = await _seed_user(seed_session, org_a)
        opportunities = await SqlAlchemyOpportunityRepository.create(seed_session, org_a)
        result = await CreateOrUpdateOpportunity(opportunities)(
            company_id=company_id, source="conversation", now=NOW
        )
        opportunity_id = result.opportunity.id

        users = SqlAlchemyUserRepository(seed_session, org_a)
        assign = AssignOpportunityOwner(opportunities, users)

        with pytest.raises(NotFoundError):
            await assign(opportunity_id, uuid4(), now=NOW)

        await assign(opportunity_id, owner_id, now=NOW)

    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        opportunities_verify = await SqlAlchemyOpportunityRepository.create(verify_session, org_a)
        reread = await opportunities_verify.get(opportunity_id)
        assert reread is not None
        assert reread.owner_id == owner_id
