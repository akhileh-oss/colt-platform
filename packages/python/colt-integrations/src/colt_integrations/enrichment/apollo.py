"""`ApolloEnrichmentProvider` (CLAUDE.md §28.1, §28.2): a real adapter for the Apollo.io API.

Verified against Apollo's own API documentation rather than guessed from training data (the
same discipline `colt_integrations.search.BraveSearchProvider` applies):

- `GET /api/v1/organizations/enrich` — `domain` query param, `x-api-key` header, response
  `{"organization": {...}}`.
- `POST /api/v1/people/match` — `email` query param, response `{"person": {...}}`, including
  an `email_status` field whose documented example value is `"verified"`.
- `POST /api/v1/mixed_companies/search` — `q_organization_name` + `page`/`per_page`, response
  `{"organizations": [...], "pagination": {...}}`.
- `POST /api/v1/mixed_people/api_search` — `q_keywords` + `page`/`per_page`, response
  `{"people": [...], "total_entries": ...}`. This endpoint deliberately returns *obfuscated*
  contact fields (no `email`, `last_name_obfuscated` instead of `last_name`) — Apollo's search
  only reveals full contact details once "unlocked" through `enrich_person`/`people/match`,
  which `DiscoveryAgent` never calls automatically (§41.3: data minimization before a tool
  call that would spend provider credits the caller didn't ask for).

**No API key is configured in this environment** (`EnrichmentSettings.api_key` is empty,
`provider` defaults to `"fake"`), so this adapter is built in full but unverified against the
live API — the same situation Milestone 10's `BraveSearchProvider` is in, and for the same
reason.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from colt_config import EnrichmentSettings
from colt_integrations.enrichment.port import CompanyCandidate, PersonCandidate
from colt_integrations.errors import (
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    classify_http_status,
)

_BASE_URL = "https://api.apollo.io/api/v1"
_BACKOFF_BASE_SECONDS = 0.5
_PROVIDER = "apollo"


class ApolloEnrichmentProvider:
    """`transport` is injectable so tests exercise the real request/response shape against
    `httpx.MockTransport` instead of the live API."""

    def __init__(
        self, settings: EnrichmentSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def search_companies(
        self, query: str, *, max_results: int = 10
    ) -> list[CompanyCandidate]:
        body = await self._request_with_retries(
            "POST",
            f"{_BASE_URL}/mixed_companies/search",
            json={"q_organization_name": query, "per_page": min(max_results, 100)},
        )
        organizations = body.get("organizations", [])
        return [self._company_candidate(org, confidence=0.6) for org in organizations[:max_results]]

    async def search_people(self, query: str, *, max_results: int = 10) -> list[PersonCandidate]:
        body = await self._request_with_retries(
            "POST",
            f"{_BASE_URL}/mixed_people/api_search",
            json={"q_keywords": query, "per_page": min(max_results, 100)},
        )
        people = body.get("people", [])
        # This endpoint returns obfuscated contact fields (no email) - see module docstring.
        return [self._person_search_candidate(person) for person in people[:max_results]]

    async def enrich_company(self, domain: str) -> CompanyCandidate | None:
        body = await self._request_with_retries(
            "GET", f"{_BASE_URL}/organizations/enrich", params={"domain": domain}
        )
        organization = body.get("organization")
        if organization is None:
            return None
        return self._company_candidate(organization, confidence=0.9)

    async def enrich_person(self, email: str) -> PersonCandidate | None:
        body = await self._request_with_retries(
            "POST", f"{_BASE_URL}/people/match", params={"email": email}
        )
        person = body.get("person")
        if person is None:
            return None
        return self._person_match_candidate(person)

    def _company_candidate(
        self, organization: dict[str, Any], *, confidence: float
    ) -> CompanyCandidate:
        return CompanyCandidate(
            name=organization.get("name", ""),
            provider=_PROVIDER,
            confidence=confidence,
            provider_id=organization.get("id"),
            domain=organization.get("primary_domain"),
            industry=organization.get("industry"),
            employee_count=organization.get("estimated_num_employees"),
            country=organization.get("country"),
            region=organization.get("state"),
            city=organization.get("city"),
            website_url=organization.get("website_url"),
            linkedin_url=organization.get("linkedin_url"),
        )

    def _person_search_candidate(self, person: dict[str, Any]) -> PersonCandidate:
        """From `mixed_people/api_search` — obfuscated; no email, low confidence (unverified
        candidate, not yet matched against a specific record)."""
        organization = person.get("organization") or {}
        return PersonCandidate(
            full_name=person.get("first_name", ""),
            provider=_PROVIDER,
            confidence=0.4,
            provider_id=person.get("id"),
            first_name=person.get("first_name"),
            title=person.get("title"),
            company_domain=organization.get("primary_domain"),
        )

    def _person_match_candidate(self, person: dict[str, Any]) -> PersonCandidate:
        """From `people/match` — a specific, named match; `match_confidence` is Apollo's own
        enum (`high`/`medium`/`low`/`none`), mapped to a 0-1 score."""
        match_confidence = {"high": 0.9, "medium": 0.6, "low": 0.3, "none": 0.0}.get(
            person.get("match_confidence", ""), 0.5
        )
        organization = person.get("organization") or {}
        email_status = person.get("email_status")
        return PersonCandidate(
            full_name=person.get("name", ""),
            provider=_PROVIDER,
            confidence=match_confidence,
            provider_id=person.get("id"),
            first_name=person.get("first_name"),
            last_name=person.get("last_name"),
            title=person.get("title"),
            email=person.get("email"),
            email_verified=(email_status == "verified") if email_status is not None else None,
            linkedin_url=person.get("linkedin_url"),
            company_domain=organization.get("primary_domain"),
        )

    async def _request_with_retries(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                return await self._request_once(method, url, **kwargs)
            except (ProviderRateLimitedError, ProviderUnavailableError, ProviderTimeoutError):
                if attempt >= self._settings.max_retries:
                    raise
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
                attempt += 1

    async def _request_once(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.timeout_seconds, transport=self._transport
            ) as client:
                response = await client.request(
                    method,
                    url,
                    headers={"x-api-key": self._settings.api_key.get_secret_value()},
                    **kwargs,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Apollo {method} {url} timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Apollo {method} {url} failed: {exc}") from exc

        if response.status_code >= 400:
            raise classify_http_status(
                response.status_code, f"Apollo {method} {url} returned {response.status_code}"
            )
        result: dict[str, Any] = response.json()
        return result
