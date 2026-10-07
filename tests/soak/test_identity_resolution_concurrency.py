"""Duplicate-creation under concurrency (CLAUDE.md §22, §27, §96, Milestone 27's "duplicate
webhook simulations" / acceptance criterion "no data corruption, duplicate sends... or
unrecoverable workflows").

`DiscoverCompany`/`DiscoverPerson`'s own dedup logic (CLAUDE.md §22) is a plain check-then-insert:
look up an existing row by normalized domain/email, and only insert when none is found. Two
concurrent calls for the same real-world company or person — exactly what happens when a signal
and an enrichment job discover the same lead at the same moment, or a webhook retry races its
own first delivery — can both pass that check before either commits, each inserting its own row
for what should be one deduplicated record. Postgres's default read-committed isolation does not
serialize this for you; only a real unique constraint does.

Found by running this test for real against real Postgres during Milestone 27: before migration
`b606dfdd0d97` (this milestone's own fix), ten concurrent `DiscoverCompany` calls for the same
domain produced ten rows, and ten concurrent `DiscoverPerson` calls for the same email produced
nine — not deduplication at all. The migration adds a partial unique index on each identity key;
`colt_db`'s repositories now translate the resulting `IntegrityError` into
`colt_domain.DuplicateIdentityError` rather than letting a raw SQLAlchemy exception (or, worse,
a silent duplicate row) reach the caller. This test's own acceptance bar is deliberately the
real safety property — at most one row ever exists — not "every caller transparently gets the
same row back": the loser of the race gets a typed, catchable error instead of corrupting data,
and the natural recovery is the same retry a Temporal activity already performs on any
unhandled exception, which then finds the winner's row on its next attempt.

**Documented, not closed, by this milestone**: the same race exists on the `provider_id`
(`source_metadata` JSONB) and `linkedin_url` matching layers too, for both companies and people —
not exercised or fixed here, since normalized-domain/email are both the easiest to reproduce and
the most common real case, and fixing every layer equally is follow-up work this milestone's own
soak run surfaced rather than closed outright.

Requires a real Postgres. Marked `soak`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from colt_application.use_cases.discover_company import DiscoverCompany
from colt_application.use_cases.discover_person import DiscoverPerson
from colt_db.models.company import CompanyModel
from colt_db.models.person import PersonModel
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_domain import DuplicateIdentityError

pytestmark = pytest.mark.soak

SessionFactory = Callable[[], Awaitable[AsyncSession]]

_CONCURRENT_CALLS = 10


async def test_concurrent_discover_company_calls_never_create_a_duplicate_row(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _org_b = two_organizations

    async def _discover_once() -> bool:
        """Returns whether this call actually created the row (vs. losing the race)."""
        session = await open_app_session()
        async with session, session.begin():
            companies = await SqlAlchemyCompanyRepository.create(session, org_a)
            try:
                _company, created = await DiscoverCompany(companies)(
                    name="Acme Corp",
                    provider="apollo",
                    confidence=0.9,
                    domain="acme.example.com",
                )
            except DuplicateIdentityError:
                return False
            return created

    results = await asyncio.gather(*(_discover_once() for _ in range(_CONCURRENT_CALLS)))

    verify = await open_app_session()
    async with verify, verify.begin():
        await SqlAlchemyCompanyRepository.create(verify, org_a)
        count = (
            await verify.execute(
                select(func.count())
                .select_from(CompanyModel)
                .where(CompanyModel.normalized_domain == "acme.example.com")
            )
        ).scalar_one()

    assert count == 1, (
        f"{_CONCURRENT_CALLS} concurrent DiscoverCompany calls for the same domain produced "
        f"{count} rows, not 1 — a duplicate-creation race, not deduplication"
    )
    assert sum(results) == 1, "exactly one concurrent call should have actually created the row"


async def test_concurrent_discover_person_calls_never_create_a_duplicate_row(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        companies = await SqlAlchemyCompanyRepository.create(seed, org_a)
        company = await companies.add(name="Acme Corp")
        company_id = company.id

    async def _discover_once() -> bool:
        session = await open_app_session()
        async with session, session.begin():
            people = await SqlAlchemyPersonRepository.create(session, org_a)
            try:
                _person, created = await DiscoverPerson(people)(
                    company_id=company_id,
                    full_name="Jane Doe",
                    provider="apollo",
                    confidence=0.9,
                    email="jane.doe@acme.example.com",
                )
            except DuplicateIdentityError:
                return False
            return created

    results = await asyncio.gather(*(_discover_once() for _ in range(_CONCURRENT_CALLS)))

    verify = await open_app_session()
    async with verify, verify.begin():
        await SqlAlchemyPersonRepository.create(verify, org_a)
        count = (
            await verify.execute(
                select(func.count())
                .select_from(PersonModel)
                .where(PersonModel.email == "jane.doe@acme.example.com")
            )
        ).scalar_one()

    assert count == 1, (
        f"{_CONCURRENT_CALLS} concurrent DiscoverPerson calls for the same email produced "
        f"{count} rows, not 1 — a duplicate-creation race, not deduplication"
    )
    assert sum(results) == 1, "exactly one concurrent call should have actually created the row"
