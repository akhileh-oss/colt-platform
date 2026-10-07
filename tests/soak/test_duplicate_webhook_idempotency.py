"""Duplicate webhook delivery (CLAUDE.md §27, §39, §96's "duplicate webhook" chaos scenario,
Milestone 27's own "duplicate webhook simulations" Build item).

The unsubscribe route's own docstring already promises a mail client's one-click retry "must
not start erroring once the first attempt has already succeeded" — but `UnsubscribeByToken` had
never actually been driven by two concurrent deliveries of the same token before this milestone.
It always called `AddSuppressionEntry` → `SuppressionRepository.add()` unconditionally, with no
existing-row check before the insert; the real safety net was `uq_suppression_entries_org_
identifier`, a unique constraint that was there from Milestone 16 but, run for real here, simply
raised a bare `IntegrityError` out of the second concurrent call — exactly the "start erroring"
the docstring promised would never happen.

This milestone's fix lives in `SqlAlchemySuppressionRepository.add()` itself: the loser of the
race now gets the winner's already-committed row back, not an exception. This test drives that
through the real use case twice, concurrently, for the same message — not just the repository
method in isolation.

Requires a real Postgres. Marked `soak`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from colt_application.use_cases.add_suppression_entry import AddSuppressionEntry
from colt_application.use_cases.unsubscribe_by_token import UnsubscribeByToken
from colt_db.models.suppression_entry import SuppressionEntryModel
from colt_db.repositories.audit_log_repository import SqlAlchemyAuditLogRepository
from colt_db.repositories.campaign_repository import SqlAlchemyCampaignRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.conversation_repository import SqlAlchemyConversationRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.message_repository import SqlAlchemyMessageRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_db.repositories.suppression_repository import SqlAlchemySuppressionRepository

pytestmark = pytest.mark.soak

SessionFactory = Callable[[], Awaitable[AsyncSession]]
NOW = datetime.now(UTC)

_CONCURRENT_DELIVERIES = 5


async def test_the_same_unsubscribe_webhook_delivered_concurrently_creates_one_suppression_entry(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        companies = await SqlAlchemyCompanyRepository.create(seed, org_a)
        company = await companies.add(name="Acme Corp")
        people = SqlAlchemyPersonRepository(seed, org_a)
        person = await people.add(
            company_id=company.id, full_name="Jane Doe", email="jane.doe@acme.example.com"
        )
        leads = SqlAlchemyLeadRepository(seed, org_a)
        lead = await leads.add(company_id=company.id, person_id=person.id)
        campaigns = SqlAlchemyCampaignRepository(seed, org_a)
        campaign = await campaigns.add(name="Q4 outbound")
        messages = await SqlAlchemyMessageRepository.create(seed, org_a)
        message = await messages.add(
            campaign_id=campaign.id,
            lead_id=lead.id,
            channel="email",
            body="Hello Jane",
            idempotency_key=str(uuid4()),
        )
        message_id = message.id

    async def _deliver_once() -> None:
        session = await open_app_session()
        async with session, session.begin():
            messages = await SqlAlchemyMessageRepository.create(session, org_a)
            leads = SqlAlchemyLeadRepository(session, org_a)
            people = SqlAlchemyPersonRepository(session, org_a)
            conversations = SqlAlchemyConversationRepository(session, org_a)
            suppressions = SqlAlchemySuppressionRepository(session, org_a)
            audit_logs = SqlAlchemyAuditLogRepository(session, org_a)
            unsubscribe_by_token = UnsubscribeByToken(
                messages,
                leads,
                people,
                conversations,
                AddSuppressionEntry(suppressions, audit_logs),
            )
            await unsubscribe_by_token(message_id=message_id, unsubscribed_at=NOW)

    # Every one of these must complete without raising — a duplicate delivery is exactly the
    # case the unsubscribe route's own docstring says must behave like the first, successful
    # one, never surface an error.
    await asyncio.gather(*(_deliver_once() for _ in range(_CONCURRENT_DELIVERIES)))

    verify = await open_app_session()
    async with verify, verify.begin():
        await SqlAlchemySuppressionRepository.create(verify, org_a)
        count = (
            await verify.execute(
                select(func.count())
                .select_from(SuppressionEntryModel)
                .where(SuppressionEntryModel.identifier == "jane.doe@acme.example.com")
            )
        ).scalar_one()

    assert count == 1, (
        f"{_CONCURRENT_DELIVERIES} concurrent deliveries of the same unsubscribe token produced "
        f"{count} suppression_entries rows, not 1"
    )
