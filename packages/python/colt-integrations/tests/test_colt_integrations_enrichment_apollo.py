"""`ApolloEnrichmentProvider` — hermetic: a real `httpx.AsyncClient` with its transport
replaced by `httpx.MockTransport`, so the request shape (headers, query/body params) and
response parsing are exercised for real, with no network call and no API key. No real API key
exists in this environment to verify against the live Apollo API — see the module docstring in
`apollo.py`.
"""

from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from colt_config import EnrichmentSettings
from colt_integrations.enrichment.apollo import ApolloEnrichmentProvider
from colt_integrations.errors import ProviderAuthenticationError, ProviderUnavailableError


def _settings() -> EnrichmentSettings:
    return EnrichmentSettings(api_key=SecretStr("apollo-test-key-not-real"), max_retries=0)


async def test_search_companies_sends_the_documented_request_shape() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "organizations": [
                    {
                        "id": "org_1",
                        "name": "Acme Rockets",
                        "primary_domain": "acme.example",
                        "industry": "Aerospace",
                        "estimated_num_employees": 250,
                        "country": "United States",
                        "state": "CA",
                        "city": "Mojave",
                        "website_url": "https://acme.example",
                        "linkedin_url": "https://linkedin.com/company/acme",
                    }
                ],
                "pagination": {"page": 1, "per_page": 10, "total_entries": 1, "total_pages": 1},
            },
        )

    provider = ApolloEnrichmentProvider(_settings(), transport=httpx.MockTransport(handler))

    candidates = await provider.search_companies("Acme Rockets", max_results=10)

    assert len(captured) == 1
    request = captured[0]
    assert request.method == "POST"
    assert request.url.path == "/api/v1/mixed_companies/search"
    assert request.headers["x-api-key"] == "apollo-test-key-not-real"

    (candidate,) = candidates
    assert candidate.name == "Acme Rockets"
    assert candidate.provider == "apollo"
    assert candidate.provider_id == "org_1"
    assert candidate.domain == "acme.example"
    assert candidate.employee_count == 250
    assert candidate.linkedin_url == "https://linkedin.com/company/acme"


async def test_search_people_maps_obfuscated_results_without_an_email() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "people": [
                    {
                        "id": "person_1",
                        "first_name": "Jane",
                        "last_name_obfuscated": "D.",
                        "title": "VP Engineering",
                        "organization": {"name": "Acme Rockets", "primary_domain": "acme.example"},
                    }
                ],
                "total_entries": 1,
            },
        )

    provider = ApolloEnrichmentProvider(_settings(), transport=httpx.MockTransport(handler))

    (candidate,) = await provider.search_people("VP Engineering")

    assert candidate.provider_id == "person_1"
    assert candidate.title == "VP Engineering"
    assert candidate.email is None
    assert candidate.company_domain == "acme.example"


async def test_enrich_company_parses_the_organization_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/organizations/enrich"
        assert request.url.params["domain"] == "acme.example"
        return httpx.Response(
            200,
            json={
                "organization": {
                    "id": "org_1",
                    "name": "Acme Rockets",
                    "primary_domain": "acme.example",
                }
            },
        )

    provider = ApolloEnrichmentProvider(_settings(), transport=httpx.MockTransport(handler))

    candidate = await provider.enrich_company("acme.example")

    assert candidate is not None
    assert candidate.name == "Acme Rockets"
    assert candidate.confidence == 0.9


async def test_enrich_company_returns_none_when_apollo_finds_no_match() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    provider = ApolloEnrichmentProvider(_settings(), transport=httpx.MockTransport(handler))

    assert await provider.enrich_company("unknown.example") is None


async def test_enrich_person_parses_the_person_envelope_and_match_confidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/people/match"
        assert request.url.params["email"] == "jane@acme.example"
        return httpx.Response(
            200,
            json={
                "request_id": 1,
                "person": {
                    "id": "person_1",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "name": "Jane Doe",
                    "email": "jane@acme.example",
                    "email_status": "verified",
                    "title": "VP Engineering",
                    "linkedin_url": "https://linkedin.com/in/janedoe",
                    "match_confidence": "high",
                    "organization": {"primary_domain": "acme.example"},
                },
            },
        )

    provider = ApolloEnrichmentProvider(_settings(), transport=httpx.MockTransport(handler))

    candidate = await provider.enrich_person("jane@acme.example")

    assert candidate is not None
    assert candidate.full_name == "Jane Doe"
    assert candidate.email == "jane@acme.example"
    assert candidate.email_verified is True
    assert candidate.confidence == 0.9
    assert candidate.company_domain == "acme.example"


async def test_a_401_response_is_classified_as_an_authentication_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    provider = ApolloEnrichmentProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderAuthenticationError):
        await provider.enrich_company("acme.example")


async def test_a_500_response_is_classified_as_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    provider = ApolloEnrichmentProvider(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderUnavailableError):
        await provider.enrich_person("jane@acme.example")
