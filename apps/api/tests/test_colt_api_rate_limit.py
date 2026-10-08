"""`colt_api.rate_limit.RateLimiter` (CLAUDE.md §37, §40, §79, Milestone 24) — hermetic: a
minimal fake standing in for `redis.asyncio.Redis`, implementing only the two methods
`RateLimiter` actually calls (`incr`/`expire`), the same injectable-client pattern
`colt_ai.AnthropicGateway`'s own tests already establish. `tests/security/test_rate_limiting.py`
separately proves the same mechanism against a real Redis.
"""

from __future__ import annotations

import pytest

from colt_api.errors import RateLimitedError
from colt_api.rate_limit import RateLimiter


class _FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expiries: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expiries[key] = seconds


async def test_requests_within_the_limit_are_allowed() -> None:
    limiter = RateLimiter(_FakeRedis())  # type: ignore[arg-type]

    for _ in range(3):
        await limiter.check("caller-a", limit=3, window_seconds=60)


async def test_a_request_beyond_the_limit_is_rejected() -> None:
    redis = _FakeRedis()
    limiter = RateLimiter(redis)  # type: ignore[arg-type]

    for _ in range(3):
        await limiter.check("caller-a", limit=3, window_seconds=60)

    with pytest.raises(RateLimitedError):
        await limiter.check("caller-a", limit=3, window_seconds=60)


async def test_different_keys_are_counted_independently() -> None:
    redis = _FakeRedis()
    limiter = RateLimiter(redis)  # type: ignore[arg-type]

    for _ in range(3):
        await limiter.check("caller-a", limit=3, window_seconds=60)

    # caller-b has made zero requests of its own - caller-a's count must not leak onto it.
    await limiter.check("caller-b", limit=3, window_seconds=60)


async def test_the_window_key_only_gets_a_ttl_on_its_first_increment() -> None:
    redis = _FakeRedis()
    limiter = RateLimiter(redis)  # type: ignore[arg-type]

    await limiter.check("caller-a", limit=10, window_seconds=30)
    await limiter.check("caller-a", limit=10, window_seconds=30)

    assert len(redis.expiries) == 1
