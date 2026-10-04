"""`BraveSearchProvider` (CLAUDE.md §28.1, §28.2): a real adapter for the Brave Web Search API.

Verified against Brave's own documentation (`GET /res/v1/web/search`, `X-Subscription-Token`
header, `web.results[].{title,url,description}` response shape) rather than guessed from
training data — the same discipline `colt_ai`'s Anthropic SDK code applies by reading the
actual installed SDK rather than recalling its shape. **No API key is configured in this
environment** (`SearchSettings.api_key` is empty, `provider` defaults to `"fake"`), so this
adapter is built in full but unverified against the live API — the same situation Milestone 08
was in with the Anthropic API, and for the same reason.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from colt_config import SearchSettings
from colt_integrations.errors import (
    ProviderError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    classify_http_status,
)
from colt_integrations.search.port import SearchResult
from colt_observability import get_logger, get_tracer

logger = get_logger(__name__)
_tracer = get_tracer(__name__)

_BASE_URL = "https://api.search.brave.com/res/v1/web/search"
_BACKOFF_BASE_SECONDS = 0.5


class BraveSearchProvider:
    """`transport` is injectable so tests exercise the real request/response shape — headers,
    query params, error classification — against `httpx.MockTransport` instead of the live API,
    the same reasoning `colt_ai.AnthropicGateway`'s injectable `client` already established."""

    def __init__(
        self, settings: SearchSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]:
        start = time.monotonic()
        with _tracer.start_as_current_span(
            "search_provider.search", attributes={"provider": "brave"}
        ) as span:
            try:
                results = await self._search_with_retries(query, max_results)
            except ProviderError as exc:
                span.set_attribute("error_code", str(exc.code))
                span.record_exception(exc)
                logger.warning(
                    "search failed",
                    extra={
                        "operation": "search_web",
                        "provider": "brave",
                        "status": "error",
                        "error_code": str(exc.code),
                        "latency_ms": (time.monotonic() - start) * 1000,
                    },
                )
                raise

            logger.info(
                "search completed",
                extra={
                    "operation": "search_web",
                    "provider": "brave",
                    "status": "ok",
                    "result_count": len(results),
                    "latency_ms": (time.monotonic() - start) * 1000,
                },
            )
            return results

    async def _search_with_retries(self, query: str, max_results: int) -> list[SearchResult]:
        attempt = 0
        while True:
            try:
                return await self._search_once(query, max_results)
            except (ProviderRateLimitedError, ProviderUnavailableError, ProviderTimeoutError):
                if attempt >= self._settings.max_retries:
                    raise
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
                attempt += 1

    async def _search_once(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.timeout_seconds, transport=self._transport
            ) as client:
                response = await client.get(
                    _BASE_URL,
                    headers={"X-Subscription-Token": self._settings.api_key.get_secret_value()},
                    params={"q": query, "count": min(max_results, 20)},
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Brave search for {query!r} timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Brave search for {query!r} failed: {exc}") from exc

        if response.status_code >= 400:
            raise classify_http_status(
                response.status_code, f"Brave search returned {response.status_code}: {query!r}"
            )

        body = response.json()
        results = body.get("web", {}).get("results", [])
        return [
            SearchResult(
                title=result.get("title", ""),
                url=result.get("url", ""),
                snippet=result.get("description", ""),
            )
            for result in results[:max_results]
        ]
