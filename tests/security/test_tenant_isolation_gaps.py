"""Tenant isolation (CLAUDE.md §9.7, §40, §45, Milestone 24's "tenant-isolation tests" Build
item) for four tables `tests/integration/test_domain_tables.py`/`test_agent_audit_tables.py`/
`test_campaign_engine.py`/`test_policy_and_approval.py`/`test_crm_sync.py` exercise functionally
(dedup, retries, suppression precedence) but never assert a real cross-tenant deny for:
`approvals`, `lead_scores`, `conversation_events`, `crm_sync_records`. Same proof shape as
`test_domain_tables.py`'s own `test_company_repository_denies_cross_tenant_read`: seed a row
under organization B, then prove organization A's own RLS-scoped session sees zero rows via a
real SQL `count(*)` — real RLS, not an in-memory assumption about it.

Requires a real Postgres. Marked `security`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from colt_db.repositories.approval_repository import SqlAlchemyApprovalRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.conversation_event_repository import (
    SqlAlchemyConversationEventRepository,
)
from colt_db.repositories.conversation_repository import SqlAlchemyConversationRepository
from colt_db.repositories.crm_sync_record_repository import SqlAlchemyCrmSyncRecordRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.lead_score_repository import SqlAlchemyLeadScoreRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository

pytestmark = pytest.mark.security

SessionFactory = Callable[[], Awaitable[AsyncSession]]
NOW = datetime.now(UTC)


@pytest.mark.asyncio
async def test_approvals_deny_cross_tenant_read(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        approvals_b = await SqlAlchemyApprovalRepository.create(seed, org_b)
        await approvals_b.add(entity_type="Message", entity_id=uuid4(), action_type="MESSAGE_SEND")

    session = await open_app_session()
    async with session, session.begin():
        await SqlAlchemyApprovalRepository.create(session, org_a)
        seen_by_a = await session.execute(text("SELECT count(*) FROM approvals"))

    assert seen_by_a.scalar_one() == 0


@pytest.mark.asyncio
async def test_lead_scores_deny_cross_tenant_read(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        companies_b = await SqlAlchemyCompanyRepository.create(seed, org_b)
        company = await companies_b.add(name="Globex Inc")
        persons_b = SqlAlchemyPersonRepository(seed, org_b)
        person = await persons_b.add(company_id=company.id, full_name="Jane Doe")
        leads_b = SqlAlchemyLeadRepository(seed, org_b)
        lead = await leads_b.add(company_id=company.id, person_id=person.id)
        lead_scores_b = await SqlAlchemyLeadScoreRepository.create(seed, org_b)
        await lead_scores_b.add(
            lead_id=lead.id,
            model_version="v1",
            icp_fit=0.8,
            persona_fit=0.8,
            signal_strength=0.8,
            timing=0.8,
            model_assessment=0.8,
            overall_score=0.8,
            reason_codes=["STRONG_FIT"],
        )

    session = await open_app_session()
    async with session, session.begin():
        await SqlAlchemyLeadScoreRepository.create(session, org_a)
        seen_by_a = await session.execute(text("SELECT count(*) FROM lead_scores"))

    assert seen_by_a.scalar_one() == 0


@pytest.mark.asyncio
async def test_conversation_events_deny_cross_tenant_read(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        companies_b = await SqlAlchemyCompanyRepository.create(seed, org_b)
        company = await companies_b.add(name="Globex Inc")
        persons_b = SqlAlchemyPersonRepository(seed, org_b)
        person = await persons_b.add(company_id=company.id, full_name="Jane Doe")
        leads_b = SqlAlchemyLeadRepository(seed, org_b)
        lead = await leads_b.add(company_id=company.id, person_id=person.id)
        conversations_b = SqlAlchemyConversationRepository(seed, org_b)
        conversation = await conversations_b.add(lead_id=lead.id, channel="email")
        conversation_events_b = await SqlAlchemyConversationEventRepository.create(seed, org_b)
        await conversation_events_b.add(
            conversation_id=conversation.id, event_type="reply_classified", occurred_at=NOW
        )

    session = await open_app_session()
    async with session, session.begin():
        await SqlAlchemyConversationEventRepository.create(session, org_a)
        seen_by_a = await session.execute(text("SELECT count(*) FROM conversation_events"))

    assert seen_by_a.scalar_one() == 0


@pytest.mark.asyncio
async def test_crm_sync_records_deny_cross_tenant_read(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        crm_sync_b = await SqlAlchemyCrmSyncRecordRepository.create(seed, org_b)
        await crm_sync_b.add(
            entity_type="Company",
            entity_id=uuid4(),
            provider_name="fake",
            provider_account_id="acct-1",
        )

    session = await open_app_session()
    async with session, session.begin():
        await SqlAlchemyCrmSyncRecordRepository.create(session, org_a)
        seen_by_a = await session.execute(text("SELECT count(*) FROM crm_sync_records"))

    assert seen_by_a.scalar_one() == 0
