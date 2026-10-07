"""DB connection drop / reconnect (CLAUDE.md §96's "DB connection drop" chaos scenario,
Milestone 27's "DB reconnects").

`colt_db.session.create_engine` deliberately uses `NullPool` (see its own docstring) — every
checkout is a brand-new physical connection, never a pooled one handed back out after the
server it was opened against restarted. That design choice already rules out the classic
"stale pooled connection raises on first use after a restart" failure mode; what is actually
worth proving for real is the part `NullPool` doesn't automatically guarantee: a write committed
before a real Postgres restart survives it, and a fresh connection opened once Postgres reports
healthy again reaches a consistent, uncorrupted database — not a hung connection, not a
partially-applied transaction.

Restarts the real local `postgres` container via `docker compose restart`. Requires `make dev`
(and the local Docker CLI, which the test shells out to directly). Marked `soak`.
"""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository

pytestmark = pytest.mark.soak

SessionFactory = Callable[[], Awaitable[AsyncSession]]

_REPO_ROOT = Path(__file__).parents[2]
_RESTART_TIMEOUT_SECONDS = 30


async def _wait_until_postgres_accepts_connections(open_app_session: SessionFactory) -> None:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + _RESTART_TIMEOUT_SECONDS
    last_error: Exception | None = None
    while loop.time() < deadline:
        try:
            session = await open_app_session()
            async with session:
                await session.execute(text("SELECT 1"))
            return
        # The restarting server can refuse outright (`OperationalError`) or reset a connection
        # mid-handshake while its listener is only partway back up (a raw `ConnectionResetError`
        # / `OSError`, not yet wrapped as a clean `OperationalError` by asyncpg/SQLAlchemy) —
        # both are the same "not ready yet," not a real failure, this early in the loop.
        except (OperationalError, DBAPIError, OSError) as exc:
            last_error = exc
            await asyncio.sleep(0.5)
    raise AssertionError(
        f"postgres did not accept connections within {_RESTART_TIMEOUT_SECONDS}s "
        f"of being restarted: {last_error}"
    )


async def test_a_committed_write_survives_a_real_postgres_restart(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _org_b = two_organizations

    session = await open_app_session()
    async with session, session.begin():
        companies = await SqlAlchemyCompanyRepository.create(session, org_a)
        before = await companies.add(name="Acme Corp Before Restart")

    subprocess.run(  # noqa: ASYNC221 - the restart itself must finish before anything else in
        # this test proceeds; there is no useful concurrent work to overlap it with.
        ["docker", "compose", "restart", "postgres"],  # noqa: S607 - the local dev CLI, not a
        # path an attacker could ever influence; this test only runs against a developer's own
        # local Docker daemon.
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        timeout=60,
    )

    await _wait_until_postgres_accepts_connections(open_app_session)

    session = await open_app_session()
    async with session, session.begin():
        companies = await SqlAlchemyCompanyRepository.create(session, org_a)
        found = await companies.get(before.id)
        after = await companies.add(name="Acme Corp After Restart")

    assert found is not None, "the pre-restart write did not survive the restart"
    assert found.name == "Acme Corp Before Restart"
    assert after.id != before.id
