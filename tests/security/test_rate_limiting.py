"""Rate limiting (CLAUDE.md §37, §40, §79, Milestone 24's "rate limiting" Build item) against a
real Redis — `apps/api/tests/test_colt_api_rate_limit.py` already proves `RateLimiter`'s own
counting/expiry logic against a hermetic fake client; this file is the security-suite sentinel
that the exact same mechanism also holds against the real `redis.asyncio.Redis` client this
runs with in every other environment, including the real `INCR`/`EXPIRE` semantics a fake could
get subtly wrong (atomicity, TTL behaviour, key independence after a flush).

Requires a real Redis (``docker compose up redis`` / ``make dev``), matching the
``REDIS_URL`` this repository's own ``.env`` points `colt_api.rate_limit` at.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import redis.asyncio as redis

from colt_api.errors import RateLimitedError
from colt_api.rate_limit import RateLimiter
from colt_config import Settings

pytestmark = pytest.mark.security


@pytest.fixture
async def real_redis_client() -> AsyncGenerator[redis.Redis]:
    client = redis.from_url(Settings().redis.url.get_secret_value(), decode_responses=True)
    try:
        await client.ping()
    except redis.ConnectionError as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no real Redis reachable for the rate-limiting sentinel: {exc}")
    yield client
    await client.aclose()


async def test_requests_within_the_limit_are_allowed_against_real_redis(
    real_redis_client: redis.Redis,
) -> None:
    limiter = RateLimiter(real_redis_client)
    # A fresh key every run - a real Redis keeps state across test runs, unlike the hermetic fake.
    key = f"sentinel-{uuid4()}"

    for _ in range(5):
        await limiter.check(key, limit=5, window_seconds=60)


async def test_a_request_beyond_the_limit_is_rejected_against_real_redis(
    real_redis_client: redis.Redis,
) -> None:
    limiter = RateLimiter(real_redis_client)
    key = f"sentinel-{uuid4()}"

    for _ in range(5):
        await limiter.check(key, limit=5, window_seconds=60)

    with pytest.raises(RateLimitedError):
        await limiter.check(key, limit=5, window_seconds=60)


async def test_different_keys_are_counted_independently_against_real_redis(
    real_redis_client: redis.Redis,
) -> None:
    limiter = RateLimiter(real_redis_client)
    key_a = f"sentinel-{uuid4()}"
    key_b = f"sentinel-{uuid4()}"

    for _ in range(5):
        await limiter.check(key_a, limit=5, window_seconds=60)

    # key_b has made zero requests of its own - key_a's real Redis count must not leak onto it.
    await limiter.check(key_b, limit=5, window_seconds=60)
