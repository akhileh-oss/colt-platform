"""Volume (CLAUDE.md §96, Milestone 27's "thousands of mocked leads" Build item) and tenant
isolation under that volume (§9.7, §27 — the literal acceptance criterion names "no... cross-
tenant access" explicitly, not just "no errors").

Creates several hundred companies/people/leads for one organization and a handful for a second,
then proves two things that only matter once there is enough real data for a wrong `WHERE`
clause or a missing RLS policy to hide among: every row this organization created is actually
there (no row silently lost or merged into another), and not one of them is visible from the
other organization's own RLS-scoped session.

**Scaled down from the literal "thousands," documented rather than silently substituted**: this
sandbox's own local Postgres container, run inside a shared CI-sized box, makes a genuine
multi-thousand-row concurrent run impractical as a routine regression test (it would make this
suite slow enough that nobody runs it); a few hundred rows already exercises the same code
paths (RLS policy evaluation, index usage, bulk query correctness) that a real multi-thousand-
row staging run would, just over less data. The real, literal "thousands... in staging" run is
`docs/runbooks/staging-soak.md`'s job, against a real environment, not this file's.

Requires a real Postgres. Marked `soak`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from colt_db.models.company import CompanyModel
from colt_db.models.lead import LeadModel
from colt_db.models.person import PersonModel
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository

pytestmark = pytest.mark.soak

SessionFactory = Callable[[], Awaitable[AsyncSession]]

_LEADS_FOR_ORG_A = 300
_LEADS_FOR_ORG_B = 20
_CONCURRENT_WRITERS = 20


async def test_volume_creation_is_complete_and_tenant_isolated(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    async def _create_leads(org_id: UUID, count: int, offset: int) -> None:
        session = await open_app_session()
        async with session, session.begin():
            companies = await SqlAlchemyCompanyRepository.create(session, org_id)
            people = SqlAlchemyPersonRepository(session, org_id)
            leads = SqlAlchemyLeadRepository(session, org_id)
            for i in range(offset, offset + count):
                company = await companies.add(name=f"Company {i}", domain=f"company{i}.example.com")
                person = await people.add(company_id=company.id, full_name=f"Person {i}")
                await leads.add(company_id=company.id, person_id=person.id)

    # Several concurrent writers per organization, not one big sequential loop — volume alone
    # proves little; volume *under concurrency* is what the acceptance criterion actually cares
    # about ("no data corruption... under realistic workloads").
    chunk = _LEADS_FOR_ORG_A // _CONCURRENT_WRITERS
    await asyncio.gather(
        *(_create_leads(org_a, chunk, offset=i * chunk) for i in range(_CONCURRENT_WRITERS)),
        _create_leads(org_b, _LEADS_FOR_ORG_B, offset=0),
    )

    verify_a = await open_app_session()
    async with verify_a, verify_a.begin():
        await SqlAlchemyLeadRepository.create(verify_a, org_a)
        counts_a = {
            "companies": (
                await verify_a.execute(select(func.count()).select_from(CompanyModel))
            ).scalar_one(),
            "people": (
                await verify_a.execute(select(func.count()).select_from(PersonModel))
            ).scalar_one(),
            "leads": (
                await verify_a.execute(select(func.count()).select_from(LeadModel))
            ).scalar_one(),
        }

    verify_b = await open_app_session()
    async with verify_b, verify_b.begin():
        await SqlAlchemyLeadRepository.create(verify_b, org_b)
        counts_b = {
            "companies": (
                await verify_b.execute(select(func.count()).select_from(CompanyModel))
            ).scalar_one(),
            "leads": (
                await verify_b.execute(select(func.count()).select_from(LeadModel))
            ).scalar_one(),
        }

    expected_a = _CONCURRENT_WRITERS * chunk
    assert counts_a["companies"] == expected_a, (
        "org A lost or gained rows under concurrent volume writes"
    )
    assert counts_a["people"] == expected_a
    assert counts_a["leads"] == expected_a
    assert counts_b["companies"] == _LEADS_FOR_ORG_B, (
        f"org B's RLS-scoped session saw {counts_b['companies']} companies, not its own "
        f"{_LEADS_FOR_ORG_B} — either cross-tenant leakage or cross-tenant data loss"
    )
    assert counts_b["leads"] == _LEADS_FOR_ORG_B
