"""Cross-tenant isolation, proven at two independent layers (CLAUDE.md §27, ADR-0005).

Requires a real Postgres — `make dev`, then `make migrate` (or the migration already applied).
Marked `integration`; excluded from `make test-unit`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from colt_db.repositories.user_repository import SqlAlchemyUserDirectory, SqlAlchemyUserRepository
from colt_db.tenancy import RlsBypassRoleError, TenantScopedRepository, assert_not_bypassing_rls

# No package __init__.py in tests/ (repository-wide convention), so this mirrors rather than
# imports conftest.py's SessionFactory alias.
SessionFactory = Callable[[], Awaitable[AsyncSession]]


async def _insert_user(
    session: AsyncSession, *, organization_id: UUID, external_auth_id: str, email: str
) -> None:
    await session.execute(text("SET LOCAL app.bypass_rls = 'true'"))
    await session.execute(
        text(
            "INSERT INTO users (organization_id, external_auth_id, email, name, role) "
            "VALUES (:org_id, :sub, :email, 'Test User', 'OWNER')"
        ),
        {"org_id": organization_id, "sub": external_auth_id, "email": email},
    )


@pytest.mark.asyncio
async def test_application_layer_denies_cross_tenant_reads(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    """Layer 1: TenantScopedRepository itself never returns another org's row."""
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        await _insert_user(seed, organization_id=org_a, external_auth_id="sub-a", email="a@acme.io")
        await _insert_user(seed, organization_id=org_b, external_auth_id="sub-b", email="b@acme.io")

    session = await open_app_session()
    async with session, session.begin():
        repo_a = await TenantScopedRepository.create(session, org_a)
        user_repo_a = SqlAlchemyUserRepository(session, repo_a.organization_id)

        users_seen_by_a = await user_repo_a.list_active()

    assert {u.email for u in users_seen_by_a} == {"a@acme.io"}


@pytest.mark.asyncio
async def test_application_layer_denies_fetching_another_orgs_user_by_id(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        await _insert_user(seed, organization_id=org_b, external_auth_id="sub-b", email="b@acme.io")

    # Read Bob's id with the bypass flag — a test-setup step, not the behaviour under test.
    session = await open_app_session()
    async with session, session.begin():
        await session.execute(text("SET LOCAL app.bypass_rls = 'true'"))
        bob_id_row = await session.execute(
            text("SELECT id FROM users WHERE organization_id = :org_b"), {"org_b": org_b}
        )
        bob_id = bob_id_row.scalar_one()

    session_a = await open_app_session()
    async with session_a, session_a.begin():
        repo_a = await TenantScopedRepository.create(session_a, org_a)
        user_repo_a = SqlAlchemyUserRepository(session_a, repo_a.organization_id)

        found = await user_repo_a.get(bob_id)

    assert found is None, "org A's repository must not be able to fetch org B's user by id"


@pytest.mark.asyncio
async def test_row_level_security_denies_a_cross_tenant_read_that_bypasses_the_repository(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    """Layer 2: even a raw query that ignores TenantScopedRepository entirely is blocked,
    because RLS is enforced at the database, not only by application code choosing to filter."""
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        await _insert_user(seed, organization_id=org_a, external_auth_id="sub-a", email="a@acme.io")
        await _insert_user(seed, organization_id=org_b, external_auth_id="sub-b", email="b@acme.io")

    session = await open_app_session()
    async with session, session.begin():
        from colt_db.tenancy import set_tenant_context

        await set_tenant_context(session, org_a)
        # A raw query, deliberately not going through any repository — proves the database
        # itself refuses the row, not just well-behaved application code.
        result = await session.execute(text("SELECT email FROM users"))
        emails = {row[0] for row in result}

    assert emails == {"a@acme.io"}


@pytest.mark.asyncio
async def test_no_tenant_context_sees_nothing_rather_than_everything(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    """Deny-by-default: a session that never sets app.current_organization_id must not leak
    every organization's data (CLAUDE.md §68: unauthorized operations fail closed)."""
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        await _insert_user(seed, organization_id=org_a, external_auth_id="sub-a", email="a@acme.io")
        await _insert_user(seed, organization_id=org_b, external_auth_id="sub-b", email="b@acme.io")

    session = await open_app_session()
    async with session, session.begin():
        result = await session.execute(text("SELECT count(*) FROM users"))
        count = result.scalar_one()

    assert count == 0


@pytest.mark.asyncio
async def test_cross_tenant_write_affects_zero_rows(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        await _insert_user(seed, organization_id=org_b, external_auth_id="sub-b", email="b@acme.io")

    session = await open_app_session()
    async with session, session.begin():
        from colt_db.tenancy import set_tenant_context

        await set_tenant_context(session, org_a)
        await session.execute(text("UPDATE users SET name = 'HACKED' WHERE email = 'b@acme.io'"))

    verify = await open_app_session()
    async with verify, verify.begin():
        await verify.execute(text("SET LOCAL app.bypass_rls = 'true'"))
        row = await verify.execute(text("SELECT name FROM users WHERE email = 'b@acme.io'"))
        assert row.scalar_one() == "Test User", "row must be unchanged by the blocked update"


@pytest.mark.asyncio
async def test_identity_resolution_finds_a_user_across_organizations(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    """The one legitimate use of the bypass path: resolving org membership from a verified
    identity, before an organization is known."""
    org_a, _org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        await _insert_user(seed, organization_id=org_a, external_auth_id="sub-a", email="a@acme.io")

    session = await open_app_session()
    async with session, session.begin():
        directory = SqlAlchemyUserDirectory(session)
        found = await directory.find_by_external_auth_id("sub-a")

    assert found is not None
    assert found.organization_id == org_a
    assert found.email == "a@acme.io"


@pytest.mark.asyncio
async def test_identity_resolution_returns_none_for_an_unknown_subject(
    open_app_session: SessionFactory,
) -> None:
    session = await open_app_session()
    async with session, session.begin():
        directory = SqlAlchemyUserDirectory(session)
        found = await directory.find_by_external_auth_id("no-such-subject")

    assert found is None


@pytest.mark.asyncio
async def test_assert_not_bypassing_rls_passes_for_the_restricted_role(
    open_app_session: SessionFactory,
) -> None:
    session = await open_app_session()
    async with session, session.begin():
        await assert_not_bypassing_rls(session)  # must not raise


@pytest.mark.asyncio
async def test_assert_not_bypassing_rls_raises_for_a_superuser_connection(
    superuser_engine: AsyncEngine,
) -> None:
    """This is the exact misconfiguration ADR-0005 documents catching."""
    factory = async_sessionmaker(superuser_engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        with pytest.raises(RlsBypassRoleError):
            await assert_not_bypassing_rls(session)
