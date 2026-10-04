"""`FakeEnrichmentProvider` — the test double CLAUDE.md §28.1 requires every adapter to have,
and `EnrichmentSettings.provider`'s configured default (no real enrichment-provider API key
exists in this environment, the same situation `colt_integrations.search`/`colt_ai` are in).
Deterministic: returns exactly the fixture candidates it was given, never a fabricated
"plausible" result (§0.4).
"""

from __future__ import annotations

from colt_integrations.enrichment.port import CompanyCandidate, PersonCandidate


class FakeEnrichmentProvider:
    def __init__(
        self,
        *,
        company_search_results: dict[str, list[CompanyCandidate]] | None = None,
        person_search_results: dict[str, list[PersonCandidate]] | None = None,
        companies_by_domain: dict[str, CompanyCandidate] | None = None,
        people_by_email: dict[str, PersonCandidate] | None = None,
    ) -> None:
        self._company_search_results = company_search_results or {}
        self._person_search_results = person_search_results or {}
        self._companies_by_domain = companies_by_domain or {}
        self._people_by_email = people_by_email or {}

    async def search_companies(
        self, query: str, *, max_results: int = 10
    ) -> list[CompanyCandidate]:
        return self._company_search_results.get(query, [])[:max_results]

    async def search_people(self, query: str, *, max_results: int = 10) -> list[PersonCandidate]:
        return self._person_search_results.get(query, [])[:max_results]

    async def enrich_company(self, domain: str) -> CompanyCandidate | None:
        return self._companies_by_domain.get(domain)

    async def enrich_person(self, email: str) -> PersonCandidate | None:
        return self._people_by_email.get(email)
