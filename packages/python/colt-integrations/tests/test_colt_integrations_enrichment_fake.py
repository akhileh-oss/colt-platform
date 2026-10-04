"""`FakeEnrichmentProvider` — deterministic fixture behavior (CLAUDE.md §0.4, §28.1)."""

from __future__ import annotations

from colt_integrations.enrichment.fake import FakeEnrichmentProvider
from colt_integrations.enrichment.port import CompanyCandidate, PersonCandidate


async def test_search_companies_returns_only_configured_fixture_results() -> None:
    candidate = CompanyCandidate(name="Acme Rockets", provider="fake", confidence=1.0)
    provider = FakeEnrichmentProvider(company_search_results={"acme": [candidate]})

    assert await provider.search_companies("acme") == [candidate]
    assert await provider.search_companies("unknown query") == []


async def test_search_people_respects_max_results() -> None:
    candidates = [
        PersonCandidate(full_name=f"Person {i}", provider="fake", confidence=1.0) for i in range(5)
    ]
    provider = FakeEnrichmentProvider(person_search_results={"eng": candidates})

    assert await provider.search_people("eng", max_results=2) == candidates[:2]


async def test_enrich_company_returns_none_when_not_configured() -> None:
    provider = FakeEnrichmentProvider()

    assert await provider.enrich_company("unknown.example") is None


async def test_enrich_person_returns_the_configured_candidate() -> None:
    candidate = PersonCandidate(full_name="Jane Doe", provider="fake", confidence=1.0)
    provider = FakeEnrichmentProvider(people_by_email={"jane@acme.example": candidate})

    assert await provider.enrich_person("jane@acme.example") == candidate
    assert await provider.enrich_person("other@acme.example") is None
