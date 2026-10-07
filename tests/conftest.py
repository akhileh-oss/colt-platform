"""Shared pytest configuration for the Colt test suites.

Suite layout (CLAUDE.md §45):

- ``tests/unit``         pure logic, no I/O
- ``tests/integration``  requires local infrastructure
- ``tests/e2e``          drives the running application
- ``tests/workflows``    Temporal workflow tests
- ``tests/security``     security and tenant-isolation invariants
- ``tests/evals``        AI evaluation suites
- ``tests/soak``         volume/chaos resilience rehearsals (Milestone 27)

Markers are declared in ``pyproject.toml``. Each suite directory applies its own marker
automatically via the mapping below, so a suite can be selected with ``-m <marker>``.

The real-Postgres fixtures below (``open_app_session``, ``two_organizations``, etc.) were
Milestone 09's own addition to ``tests/integration/conftest.py`` — Milestone 24 moved them up
here because ``tests/security/``'s own tenant-isolation tests (CLAUDE.md §9.7, §45's "security
and tenant-isolation invariants") need exactly the same real, RLS-enforcing Postgres connection
``tests/integration/`` already established, and a sibling directory's ``conftest.py`` is not on
either suite's fixture-resolution path — only a shared ancestor's is. Moving the fixtures here,
rather than duplicating them, is what makes them visible to both suites at once.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_SUITE_MARKERS = {
    "integration": "integration",
    "e2e": "e2e",
    "workflows": "workflows",
    "security": "security",
    "evals": "evals",
    "soak": "soak",
}

_TESTS_ROOT = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply the suite marker implied by each test's directory."""
    for item in items:
        try:
            relative = Path(item.path).relative_to(_TESTS_ROOT)
        except ValueError:
            continue
        suite = relative.parts[0] if relative.parts else ""
        marker = _SUITE_MARKERS.get(suite)
        if marker is not None:
            item.add_marker(getattr(pytest.mark, marker))


# --- Real-Postgres fixtures (CLAUDE.md §45.2) -----------------------------------------------
#
# Two engines, deliberately: `app_engine` connects as `colt_app`, the restricted role the
# running application actually uses — this is what every test should exercise by default,
# since it is what proves RLS provides real protection (ADR-0005: a superuser connection makes
# RLS silently inert). `superuser_engine` connects as `colt`, the migration role, and exists
# only for the one test that must prove `assert_not_bypassing_rls` catches exactly that
# misconfiguration.

APP_URL = "postgresql+asyncpg://colt_app:colt_app@localhost:5432/colt"
SUPERUSER_URL = "postgresql+asyncpg://colt:colt@localhost:5432/colt"

#: A callable returning a fresh session bound to the restricted app role. A factory, not a
#: single shared session: several tests need one session per simulated request (one to seed as
#: org A, a separate one scoped to org B) rather than one long-lived transaction, matching how a
#: real request's session lifecycle actually works.
SessionFactory = Callable[[], Awaitable[AsyncSession]]


@pytest_asyncio.fixture
async def app_engine() -> AsyncIterator[AsyncEngine]:
    # Function-scoped, not session-scoped: asyncpg's connection pool is bound to the event loop
    # it was created on, and pytest-asyncio gives each test function its own loop by default.
    # A session-scoped engine would work in the first test and fail every one after with
    # "attached to a different loop."
    engine = create_async_engine(APP_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def superuser_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(SUPERUSER_URL, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(superuser_engine: AsyncEngine) -> AsyncIterator[None]:
    """Every test starts with empty tenancy tables, regardless of what an earlier test left."""
    yield
    async with superuser_engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, organizations CASCADE"))


@pytest.fixture(autouse=True)
def _reset_default_engine() -> Iterator[None]:
    """`colt_db.get_default_engine()` is `lru_cache`d for one-per-*process* (correct for a real
    running server, which has one event loop for its whole lifetime).

    `colt_api.app.create_app()`'s own lifespan already disposes this engine correctly on
    shutdown — but through `FastAPI` `TestClient`, that shutdown runs inside TestClient's own
    background event loop (an anyio portal thread), not pytest-asyncio's per-test loop. This
    fixture must not `await` anything itself — doing so from pytest-asyncio's loop against an
    engine created in TestClient's loop reproduces the exact "attached to a different loop"
    error one level deeper, in cleanup code instead of the test. Clearing the cache (a plain,
    synchronous dict operation) is enough: the disposed engine is simply forgotten, and the next
    test's `create_app()` builds a fresh one from scratch, unbound to any prior loop.
    """
    from colt_db.session import get_default_engine

    yield
    get_default_engine.cache_clear()


@pytest_asyncio.fixture
async def open_app_session(app_engine: AsyncEngine) -> SessionFactory:
    factory = async_sessionmaker(app_engine, expire_on_commit=False)

    async def _open() -> AsyncSession:
        return factory()

    return _open


@pytest_asyncio.fixture
async def two_organizations(open_app_session: SessionFactory) -> tuple[UUID, UUID]:
    """Seed two organizations, return their ids. Uses the bypass flag, same as the real
    identity-resolution code path does — not superuser access."""
    session = await open_app_session()
    async with session, session.begin():
        await session.execute(text("SET LOCAL app.bypass_rls = 'true'"))
        org_a_id, org_b_id = uuid4(), uuid4()
        await session.execute(
            text(
                "INSERT INTO organizations (id, name, slug) VALUES "
                "(:id_a, 'Org A', 'org-a-' || :suffix), "
                "(:id_b, 'Org B', 'org-b-' || :suffix)"
            ),
            {"id_a": org_a_id, "id_b": org_b_id, "suffix": str(uuid4())[:8]},
        )
    return org_a_id, org_b_id
