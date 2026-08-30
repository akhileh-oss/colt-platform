"""Milestone 05 — domain + database foundation (CLAUDE.md §10.3-§10.14, §48, §68).

Covers what Milestone 04's `test_tenant_isolation.py` already proves for `users` extended across
every new table: RLS is enabled/forced/policied everywhere it should be, repositories deny
cross-tenant access, and the constraints the migration declares (foreign keys, CHECKs, partial
unique indexes) are real — proven by trying to violate them, not by reading the migration source.

Requires a real Postgres — `make dev`, then `make migrate` (or the migration already applied).
Marked `integration`; excluded from `make test-unit`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from colt_db.repositories.audit_log_repository import SqlAlchemyAuditLogRepository
from colt_db.repositories.campaign_repository import SqlAlchemyCampaignRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.conversation_repository import SqlAlchemyConversationRepository
from colt_db.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.message_repository import SqlAlchemyMessageRepository
from colt_db.repositories.opportunity_repository import SqlAlchemyOpportunityRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_db.repositories.signal_repository import SqlAlchemySignalRepository
from colt_db.tenancy import set_tenant_context
from colt_domain import ConversationState, LeadStatus, PipelineStage

# No package __init__.py in tests/ (repository-wide convention), so this mirrors rather than
# imports conftest.py's SessionFactory alias.
SessionFactory = Callable[[], Awaitable[AsyncSession]]

_NEW_TENANT_TABLES = (
    "companies",
    "people",
    "signals",
    "evidence",
    "leads",
    "campaigns",
    "messages",
    "conversations",
    "opportunities",
    "audit_logs",
)


@pytest.mark.asyncio
async def test_every_new_table_has_rls_enabled_and_forced(
    open_app_session: SessionFactory,
) -> None:
    session = await open_app_session()
    async with session, session.begin():
        result = await session.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = ANY(:tables)"
            ),
            {"tables": list(_NEW_TENANT_TABLES)},
        )
        rows = {row.relname: (row.relrowsecurity, row.relforcerowsecurity) for row in result}

    assert set(rows) == set(_NEW_TENANT_TABLES), "every new table must exist"
    for table, (enabled, forced) in rows.items():
        assert enabled, f"{table} must have Row-Level Security enabled"
        assert forced, f"{table} must FORCE Row-Level Security (owner/migration role included)"


@pytest.mark.asyncio
async def test_every_new_table_has_a_tenant_isolation_policy(
    open_app_session: SessionFactory,
) -> None:
    session = await open_app_session()
    async with session, session.begin():
        result = await session.execute(
            text("SELECT tablename FROM pg_policies WHERE policyname = 'tenant_isolation'")
        )
        tables_with_policy = {row.tablename for row in result}

    assert set(_NEW_TENANT_TABLES) <= tables_with_policy


@pytest.mark.asyncio
async def test_company_repository_denies_cross_tenant_read(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        repo_b = await SqlAlchemyCompanyRepository.create(seed, org_b)
        await repo_b.add(name="Globex Inc")

    session = await open_app_session()
    async with session, session.begin():
        repo_a = await SqlAlchemyCompanyRepository.create(session, org_a)
        companies_seen_by_a = await session.execute(text("SELECT count(*) FROM companies"))

    assert companies_seen_by_a.scalar_one() == 0
    assert repo_a.organization_id == org_a


@pytest.mark.asyncio
async def test_lead_repository_denies_fetching_another_orgs_lead_by_id(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        company_repo = await SqlAlchemyCompanyRepository.create(seed, org_b)
        company = await company_repo.add(name="Globex Inc")
        person_id = (
            await seed.execute(
                text(
                    "INSERT INTO people (organization_id, company_id, full_name) "
                    "VALUES (:org_id, :company_id, 'Bob Smith') RETURNING id"
                ),
                {"org_id": org_b, "company_id": company.id},
            )
        ).scalar_one()
        lead_repo = SqlAlchemyLeadRepository(seed, org_b)
        lead = await lead_repo.add(company_id=company.id, person_id=person_id)

    session = await open_app_session()
    async with session, session.begin():
        repo_a = await SqlAlchemyLeadRepository.create(session, org_a)
        found = await repo_a.get(lead.id)

    assert found is None, "org A's repository must not be able to fetch org B's lead by id"


@pytest.mark.asyncio
async def test_person_requires_an_existing_company(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _org_b = two_organizations

    session = await open_app_session()
    async with session, session.begin():
        await set_tenant_context(session, org_a)
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO people (organization_id, company_id, full_name) "
                    "VALUES (:org_id, :company_id, 'Nobody')"
                ),
                {"org_id": org_a, "company_id": uuid4()},
            )


@pytest.mark.asyncio
async def test_lead_status_check_constraint_rejects_an_invented_status(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    """CLAUDE.md §11: 'Do not let LLMs invent arbitrary statuses' — enforced in the database,
    not only by the `LeadStatus` enum on the way in."""
    org_a, _org_b = two_organizations

    session = await open_app_session()
    async with session, session.begin():
        company_repo = await SqlAlchemyCompanyRepository.create(session, org_a)
        company = await company_repo.add(name="Acme Corp")
        person_id = (
            await session.execute(
                text(
                    "INSERT INTO people (organization_id, company_id, full_name) "
                    "VALUES (:org_id, :company_id, 'Alice Doe') RETURNING id"
                ),
                {"org_id": org_a, "company_id": company.id},
            )
        ).scalar_one()

        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO leads (organization_id, company_id, person_id, status) "
                    "VALUES (:org_id, :company_id, :person_id, 'MADE_UP_STATUS')"
                ),
                {"org_id": org_a, "company_id": company.id, "person_id": person_id},
            )


@pytest.mark.asyncio
async def test_conversation_state_check_constraint_rejects_an_invented_state(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _org_b = two_organizations

    session = await open_app_session()
    async with session, session.begin():
        company_repo = await SqlAlchemyCompanyRepository.create(session, org_a)
        company = await company_repo.add(name="Acme Corp")
        person_id = (
            await session.execute(
                text(
                    "INSERT INTO people (organization_id, company_id, full_name) "
                    "VALUES (:org_id, :company_id, 'Alice Doe') RETURNING id"
                ),
                {"org_id": org_a, "company_id": company.id},
            )
        ).scalar_one()
        lead_repo = SqlAlchemyLeadRepository(session, org_a)
        lead = await lead_repo.add(company_id=company.id, person_id=person_id)

        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO conversations (organization_id, lead_id, channel, state) "
                    "VALUES (:org_id, :lead_id, 'email', 'MADE_UP_STATE')"
                ),
                {"org_id": org_a, "lead_id": lead.id},
            )


@pytest.mark.asyncio
async def test_message_idempotency_key_is_unique_per_organization_not_globally(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    """CLAUDE.md §2.9, §24.4: a retried send must not double-send. The uniqueness is
    per-organization (a partial index), not a global accident of two orgs sharing a key."""
    org_a, org_b = two_organizations

    async def _seed_message(session: AsyncSession, org_id: UUID, key: str) -> None:
        company_repo = await SqlAlchemyCompanyRepository.create(session, org_id)
        company = await company_repo.add(name="Acme Corp")
        person_id = (
            await session.execute(
                text(
                    "INSERT INTO people (organization_id, company_id, full_name) "
                    "VALUES (:org_id, :company_id, 'Alice Doe') RETURNING id"
                ),
                {"org_id": org_id, "company_id": company.id},
            )
        ).scalar_one()
        lead_repo = SqlAlchemyLeadRepository(session, org_id)
        lead = await lead_repo.add(company_id=company.id, person_id=person_id)
        campaign_id = (
            await session.execute(
                text(
                    "INSERT INTO campaigns (organization_id, name) "
                    "VALUES (:org_id, 'Q1 Outbound') RETURNING id"
                ),
                {"org_id": org_id},
            )
        ).scalar_one()
        await session.execute(
            text(
                "INSERT INTO messages "
                "(organization_id, campaign_id, lead_id, channel, body, idempotency_key) "
                "VALUES (:org_id, :campaign_id, :lead_id, 'email', 'hello', :key)"
            ),
            {"org_id": org_id, "campaign_id": campaign_id, "lead_id": lead.id, "key": key},
        )

    session_a = await open_app_session()
    async with session_a, session_a.begin():
        await _seed_message(session_a, org_a, "send-42")

    # Same key, different organization: must succeed — the constraint is per-organization.
    session_b = await open_app_session()
    async with session_b, session_b.begin():
        await _seed_message(session_b, org_b, "send-42")

    # Same key, same organization again: must be rejected.
    session_a2 = await open_app_session()
    async with session_a2, session_a2.begin():
        with pytest.raises(IntegrityError):
            await _seed_message(session_a2, org_a, "send-42")


@pytest.mark.asyncio
async def test_lead_is_unique_per_person_within_an_organization(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _org_b = two_organizations

    session = await open_app_session()
    async with session, session.begin():
        company_repo = await SqlAlchemyCompanyRepository.create(session, org_a)
        company = await company_repo.add(name="Acme Corp")
        person_id = (
            await session.execute(
                text(
                    "INSERT INTO people (organization_id, company_id, full_name) "
                    "VALUES (:org_id, :company_id, 'Alice Doe') RETURNING id"
                ),
                {"org_id": org_a, "company_id": company.id},
            )
        ).scalar_one()
        lead_repo = SqlAlchemyLeadRepository(session, org_a)
        await lead_repo.add(company_id=company.id, person_id=person_id)

        with pytest.raises(IntegrityError):
            await lead_repo.add(company_id=company.id, person_id=person_id)


@pytest.mark.asyncio
async def test_full_entity_chain_roundtrips_through_repositories(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    """Company -> Person -> Lead -> Conversation -> Campaign -> Message -> Opportunity, each
    created through its repository and read back — proving the whole foreign-key chain the
    migration declares is actually satisfiable, not just syntactically valid DDL."""
    org_a, _org_b = two_organizations

    session = await open_app_session()
    async with session, session.begin():
        company_repo = await SqlAlchemyCompanyRepository.create(session, org_a)
        company = await company_repo.add(name="Acme Corp", domain="acme.example")
        assert (await company_repo.get(company.id)) == company

        person_repo = SqlAlchemyPersonRepository(session, org_a)
        person = await person_repo.add(company_id=company.id, full_name="Alice Doe")
        assert (await person_repo.get(person.id)) == person

        lead_repo = SqlAlchemyLeadRepository(session, org_a)
        lead = await lead_repo.add(
            company_id=company.id, person_id=person.id, status=LeadStatus.QUALIFIED
        )
        assert lead.status is LeadStatus.QUALIFIED

        conversation_repo = SqlAlchemyConversationRepository(session, org_a)
        conversation = await conversation_repo.add(lead_id=lead.id, channel="email")
        assert conversation.state is ConversationState.OPEN

        campaign_repo = SqlAlchemyCampaignRepository(session, org_a)
        campaign = await campaign_repo.add(name="Q1 Outbound")

        message_repo = SqlAlchemyMessageRepository(session, org_a)
        message = await message_repo.add(
            campaign_id=campaign.id,
            lead_id=lead.id,
            conversation_id=conversation.id,
            channel="email",
            body="Hi Alice, ...",
            idempotency_key="chain-test-1",
        )
        assert (await message_repo.get_by_idempotency_key("chain-test-1")) == message

        opportunity_repo = SqlAlchemyOpportunityRepository(session, org_a)
        opportunity = await opportunity_repo.add(
            company_id=company.id,
            primary_person_id=person.id,
            lead_id=lead.id,
            pipeline_stage=PipelineStage.DISCOVERY,
        )
        assert opportunity.pipeline_stage is PipelineStage.DISCOVERY

        evidence_repo = SqlAlchemyEvidenceRepository(session, org_a)
        evidence = await evidence_repo.add(
            entity_type="company",
            entity_id=company.id,
            claim="Acme Corp raised a Series B",
            source_url="https://example.test/news/acme-series-b",
            observed_at=datetime.now(UTC),
        )
        assert evidence.verification_status == "UNVERIFIED"

        signal_repo = SqlAlchemySignalRepository(session, org_a)
        signal = await signal_repo.add(
            company_id=company.id,
            person_id=person.id,
            signal_type="funding",
            observed_at=datetime.now(UTC),
        )
        assert signal.company_id == company.id

        audit_repo = SqlAlchemyAuditLogRepository(session, org_a)
        audit_entry = await audit_repo.record(
            actor_type="user", action="lead.created", entity_type="lead", entity_id=lead.id
        )
        assert audit_entry.action == "lead.created"
