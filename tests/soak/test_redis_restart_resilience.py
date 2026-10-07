"""Redis restart (CLAUDE.md §96's "Redis restart" chaos scenario, Milestone 27's "Redis
failures").

Unlike `colt_db`'s `NullPool`-per-checkout engine, `colt_api.rate_limit.get_redis_client` is a
genuine process-wide singleton (`redis.asyncio.Redis`, cached at module scope) — the one place
in this codebase a connection is actually expected to be reused across many calls over a long
process lifetime, and so the one place a real server restart could plausibly leave it in a
broken state that never recovers without a process restart. `redis-py`'s async client is
documented to reconnect transparently on the next command after a connection error; this test
proves that holds against a real Redis, not just the client library's own claim.

Restarts the real local `redis` container via `docker compose restart`. Requires `make dev`.
Marked `soak`.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
import redis.asyncio as redis

from colt_api.rate_limit import RateLimiter
from colt_config import Settings

pytestmark = pytest.mark.soak

_REPO_ROOT = Path(__file__).parents[2]
_RESTART_TIMEOUT_SECONDS = 30


async def _wait_until_redis_accepts_commands(client: redis.Redis) -> None:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + _RESTART_TIMEOUT_SECONDS
    last_error: Exception | None = None
    while loop.time() < deadline:
        try:
            await client.ping()
            return
        except (redis.ConnectionError, redis.TimeoutError, OSError) as exc:
            last_error = exc
            await asyncio.sleep(0.5)
    raise AssertionError(
        f"redis did not accept commands within {_RESTART_TIMEOUT_SECONDS}s "
        f"of being restarted: {last_error}"
    )


async def test_the_rate_limiter_recovers_after_a_real_redis_restart() -> None:
    client = redis.from_url(Settings().redis.url.get_secret_value(), decode_responses=True)
    limiter = RateLimiter(client)
    key = f"soak-{uuid4()}"

    try:
        await limiter.check(key, limit=100, window_seconds=60)

        subprocess.run(  # noqa: ASYNC221 - the restart must finish before anything else
            # proceeds; there is no useful concurrent work to overlap it with.
            ["docker", "compose", "restart", "redis"],  # noqa: S607 - the local dev CLI, not a
            # path an attacker could ever influence; this test only runs against a developer's
            # own local Docker daemon.
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            timeout=60,
        )

        await _wait_until_redis_accepts_commands(client)

        # A fresh key: the restart itself clears Redis's in-memory state (CLAUDE.md names no
        # persistence requirement for rate-limit counters), so this is proving reconnection
        # recovers cleanly, not that counts survive — a real Redis restart losing in-memory
        # rate-limit state is an accepted, documented consequence, never data corruption.
        await limiter.check(f"{key}-post-restart", limit=100, window_seconds=60)
    finally:
        await client.aclose()
