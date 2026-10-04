from __future__ import annotations

from colt_integrations.search.fake import FakeSearchProvider
from colt_integrations.search.port import SearchResult


async def test_returns_fixture_results_for_a_configured_query() -> None:
    result = SearchResult(title="Acme", url="https://acme.example", snippet="Acme Corp")
    provider = FakeSearchProvider({"acme": [result]})

    results = await provider.search("acme")

    assert results == [result]


async def test_returns_nothing_for_an_unconfigured_query() -> None:
    provider = FakeSearchProvider()

    results = await provider.search("anything")

    assert results == []


async def test_respects_max_results() -> None:
    results = [
        SearchResult(title=f"r{i}", url=f"https://x.example/{i}", snippet="") for i in range(5)
    ]
    provider = FakeSearchProvider({"q": results})

    limited = await provider.search("q", max_results=2)

    assert len(limited) == 2
