"""Async engine and session factory (CLAUDE.md §9.1).

One engine per process, created from settings — never a module-level connection string, never
`os.getenv` here (CLAUDE.md §7).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from colt_config import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Build an engine with no connection pooling.

    A pooled engine binds each connection to the event loop that first checked it out, and can
    later hand it back out on a checkout from a different loop. A real deployed process has
    exactly one loop for its whole lifetime, so this never bites there — but FastAPI's
    `TestClient` (via `httpx2`) runs lifespan startup and per-request handling through separate
    internal loops, so a pooled engine fails cross-loop mid-suite with "attached to a different
    loop" errors surfaced during connection close/recycle. `NullPool` opens a fresh connection
    per checkout and closes it on release, so no connection is ever reused across a loop
    boundary — trading pooling's throughput for correctness that holds in both a real process
    and a multi-loop test harness (CLAUDE.md §105: reliability and testability over premature
    performance optimization at this stage).
    """
    return create_async_engine(
        settings.url.get_secret_value(),
        echo=settings.echo,
        poolclass=NullPool,
    )


@lru_cache(maxsize=1)
def get_default_engine() -> AsyncEngine:
    """The process-wide engine, built from settings on first use.

    Cached like `colt_config.get_settings`. Shared by `get_session()` and by the API's
    readiness check and shutdown handler, so request handling and health probes go through the
    same engine rather than two independent ones to the same database. Tests that need a
    different database must construct their own engine with `create_engine` rather than relying
    on this one.
    """
    from colt_config import get_settings

    return create_engine(get_settings().database)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-dependency-shaped session provider over the process-wide engine."""
    factory = make_session_factory(get_default_engine())
    async with factory() as session:
        yield session
