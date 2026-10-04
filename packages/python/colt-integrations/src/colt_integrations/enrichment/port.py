"""The enrichment provider port (CLAUDE.md §2.7, §28.2's `EnrichmentProvider`, §16.1's Data
tools: `search_companies`/`search_people`/`enrich_company`/`enrich_person`).

`confidence` and `provider`/`provider_id` are on every candidate because §12.3 requires
`DiscoveryAgent`'s output to "include source/provider identifiers," and §12.4 requires
`EnrichmentAgent` to use "source precedence and confidence rules" rather than silently
overwriting higher-confidence data — both need these on the candidate itself, not bolted on
after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CompanyCandidate:
    name: str
    provider: str
    confidence: float
    provider_id: str | None = None
    domain: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    website_url: str | None = None
    linkedin_url: str | None = None


@dataclass(frozen=True, slots=True)
class PersonCandidate:
    full_name: str
    provider: str
    confidence: float
    provider_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    linkedin_url: str | None = None
    company_domain: str | None = None


class EnrichmentProvider(Protocol):
    async def search_companies(
        self, query: str, *, max_results: int = 10
    ) -> list[CompanyCandidate]: ...

    async def search_people(
        self, query: str, *, max_results: int = 10
    ) -> list[PersonCandidate]: ...

    async def enrich_company(self, domain: str) -> CompanyCandidate | None: ...

    async def enrich_person(self, email: str) -> PersonCandidate | None: ...
