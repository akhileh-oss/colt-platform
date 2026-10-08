"""Redis-backed rate limiting (CLAUDE.md §37, §40, §79, Milestone 24).

A fixed-window counter: ``INCR`` a key scoped to one caller-chosen bucket name plus the current
window index, set the key's TTL the first time it is created, and reject once the window's count
exceeds the configured limit. CLAUDE.md names rate limiting as a Build item without specifying
an algorithm — a fixed window (rather than a sliding window or token bucket) is this milestone's
own documented, minimal choice, the same "the milestone building it makes the documented call"
pattern this codebase already establishes elsewhere (e.g. `CampaignStatus`, `revenue_attribution`).

§79 names five categories to rate-limit: authentication-sensitive endpoints, expensive AI
endpoints, search/research endpoints, outbound action endpoints, and webhook endpoints. Of
those, this codebase has no direct HTTP route in the first three today — authentication is
delegated entirely to Keycloak (no local login endpoint), and every AI/search operation runs
inside a Temporal workflow/activity, never synchronously inside an HTTP handler (CLAUDE.md
§2.5's "workflows own sequencing") — so there is nothing for an HTTP-layer limiter to protect
there yet. "Outbound action endpoints" already has its own, different throttle
(`colt_policy.outbound`'s `rate_limit_ok` check inside `SendMessage`, per-campaign, Milestone
16-18). That leaves "webhook endpoints" as this milestone's own concrete target: the
deliberately unauthenticated `POST /unsubscribe/{organization_id}/{message_id}` route, keyed by
the `(organization_id, message_id)` pair in its own URL rather than by client IP — a brute-force
attempt against one unsubscribe token looks the same whether or not it comes from behind a
shared NAT/proxy, and keying by the token itself needs no IP-extraction logic at all. The
`rate_limit()` dependency factory below is written generically so any other route can adopt it
the same way, by depending on ``Depends(rate_limit("some-bucket", lambda request: "some-key"))``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import redis.asyncio as redis
from fastapi import Request

from colt_api.errors import RateLimitedError
from colt_config import Settings, get_settings

_client: redis.Redis | None = None


def get_redis_client(settings: Settings) -> redis.Redis:
    """The process-wide Redis client, built from settings on first use.

    Not `lru_cache`d like `colt_db.get_default_engine`: `redis.asyncio.Redis` is not hashable
    on its settings argument the same way, and a single module-level instance serves exactly as
    well here since this client is never reconfigured mid-process.
    """
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis.url.get_secret_value(), decode_responses=True)
    return _client


async def close_redis_client() -> None:
    """Release the process-wide client. Called from the API's shutdown lifespan."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class RateLimiter:
    """A fixed-window limiter over an injected Redis client — injected so tests exercise this
    class's own counting/expiry logic against a real or fake client without needing a running
    Redis, the same "injectable client" pattern `colt_ai.AnthropicGateway` already establishes.
    """

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        """Raise `RateLimitedError` once more than `limit` calls land in the current window for
        `key`. The window index is derived from wall-clock time, so two callers computing it at
        the same moment always agree on the same Redis key without coordinating."""
        window_index = int(time.time()) // window_seconds
        bucket = f"ratelimit:{key}:{window_index}"
        count = await self._client.incr(bucket)
        if count == 1:
            await self._client.expire(bucket, window_seconds)
        if count > limit:
            raise RateLimitedError(
                f"Rate limit exceeded: at most {limit} requests per {window_seconds}s.",
                details={"limit": limit, "window_seconds": window_seconds},
            )


def rate_limit(
    bucket_name: str,
    key_fn: Callable[[Request], Awaitable[str] | str],
    *,
    limit: int,
    window_seconds: int = 60,
) -> Callable[[Request], Awaitable[None]]:
    """A dependency factory: ``Depends(rate_limit("unsubscribe", key_fn, limit=10))``.

    `key_fn` receives the request and returns the identity to limit by (a token, an org+entity
    pair, a principal id, ...) — the caller decides what "one caller" means for its own route,
    this module only does the counting.
    """

    async def _check(request: Request) -> None:
        settings = get_settings()
        key = key_fn(request)
        if not isinstance(key, str):
            key = await key
        limiter = RateLimiter(get_redis_client(settings))
        await limiter.check(f"{bucket_name}:{key}", limit=limit, window_seconds=window_seconds)

    return _check
