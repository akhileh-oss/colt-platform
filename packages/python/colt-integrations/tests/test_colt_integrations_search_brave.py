"""`BraveSearchProvider` — hermetic: a real `httpx.AsyncClient` with its transport replaced by
`httpx.MockTransport`, so the request shape (headers, query params) and response parsing are
exercised for real, with no network call and no API key. No real API key exists in this
environment to verify against the live Brave API — see the module docstring in `brave.py`.
"""

from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from colt_config import SearchSettings
from colt_integrations.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from colt_integrations.search.brave import BraveSearchProvider
from colt_integrations.search.port import SearchResult


def _settings() -> SearchSettings:
    return SearchSettings(api_key=SecretStr("brave-test-key-not-real"), max_retries=0)


def _brave_response(results: list[dict[str, str]]) -> httpx.Response:
    return httpx.Response(200, json={"web": {"results": results}})


async def test_sends_the_documented_request_shape_and_parses_results() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _brave_response(
            [{"title": "Acme Corp", "url": "https://acme.example", "description": "Rockets."}]
        )

    provider = BraveSearchProvider(_settings(), transport=httpx.MockTransport(handler))

    results = await provider.search("acme corp", max_results=5)

    assert len(captured) == 1
    request = captured[0]
    assert request.url.path == "/res/v1/web/search"
    assert request.headers["x-subscription-token"] == "brave-test-key-not-real"
    assert request.url.params["q"] == "acme corp"
    assert request.url.params["count"] == "5"

    assert results == [
        SearchResult(title="Acme Corp", url="https://acme.example", snippet="Rockets.")
    ]


async def test_count_param_is_capped_at_twenty() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _brave_response([])

    provider = BraveSearchProvider(_settings(), transport=httpx.MockTransport(handler))
    await provider.search("q", max_results=50)

    assert captured[0].url.params["count"] == "20"


async def test_a_401_response_is_classified_as_an_authentication_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid token"})

    provider = BraveSearchProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderAuthenticationError):
        await provider.search("q")


async def test_a_429_response_is_classified_as_rate_limited_and_retried() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return _brave_response([{"title": "ok", "url": "https://ok.example", "description": ""}])

    settings = SearchSettings(api_key=SecretStr("brave-test-key-not-real"), max_retries=1)
    provider = BraveSearchProvider(settings, transport=httpx.MockTransport(handler))

    results = await provider.search("q")

    assert attempts == 2
    assert results[0].title == "ok"


async def test_a_429_response_raises_once_retries_are_exhausted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    provider = BraveSearchProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderRateLimitedError):
        await provider.search("q")


async def test_a_500_response_is_classified_as_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    provider = BraveSearchProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderUnavailableError):
        await provider.search("q")
