"""`DiscoverCompany` (CLAUDE.md §12.3, §22) — the use case `colt-agents`' `search_companies`
tool calls to turn one discovered candidate into a deduplicated `Company` row.

Takes plain scalar arguments, not a `colt_integrations.enrichment.CompanyCandidate` — this
package depends only on `colt_domain`/`colt_policy` (CLAUDE.md §5), never on the provider-adapter
layer; the typed tool that calls this (which does depend on both) is what unpacks a
provider-specific candidate into these arguments, the same separation
`colt_agents.tools.record_evidence` already draws against `RecordEvidence`.

Matches in priority order, per §22's layered algorithm, and never on name alone: exact
`provider_id` where trustworthy, then normalized domain, then normalized LinkedIn URL. A match
at any layer returns the existing row unchanged — row-level enrichment (field-by-field, with
confidence precedence) is `EnrichCompany`'s separate job (§12.4), not this one's.
"""

from __future__ import annotations

from colt_application.identity import normalize_domain, normalize_linkedin_url
from colt_application.ports.company_repository import CompanyRepository
from colt_domain import Company


class DiscoverCompany:
    def __init__(self, companies: CompanyRepository) -> None:
        self._companies = companies

    async def __call__(
        self,
        *,
        name: str,
        provider: str,
        confidence: float,
        provider_id: str | None = None,
        domain: str | None = None,
        industry: str | None = None,
        employee_count: int | None = None,
        country: str | None = None,
        region: str | None = None,
        city: str | None = None,
        website_url: str | None = None,
        linkedin_url: str | None = None,
    ) -> tuple[Company, bool]:
        """Returns `(company, created)` — `created` is `False` on a dedup hit."""
        if provider_id is not None:
            existing = await self._companies.find_by_provider_id(provider, provider_id)
            if existing is not None:
                return existing, False

        normalized_domain = normalize_domain(domain) if domain is not None else None
        if normalized_domain is not None:
            existing = await self._companies.find_by_normalized_domain(normalized_domain)
            if existing is not None:
                return existing, False

        normalized_linkedin = (
            normalize_linkedin_url(linkedin_url) if linkedin_url is not None else None
        )
        if normalized_linkedin is not None:
            existing = await self._companies.find_by_linkedin_url(normalized_linkedin)
            if existing is not None:
                return existing, False

        company = await self._companies.add(
            name=name,
            domain=domain,
            normalized_domain=normalized_domain,
            industry=industry,
            employee_count=employee_count,
            country=country,
            region=region,
            city=city,
            website_url=website_url,
            linkedin_url=normalized_linkedin,
            source_metadata={
                "provider": provider,
                "provider_id": provider_id,
                "confidence": confidence,
            },
        )
        return company, True
