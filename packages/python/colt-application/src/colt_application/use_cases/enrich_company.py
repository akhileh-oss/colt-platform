"""`EnrichCompany` (CLAUDE.md §12.4) — the use case `colt-agents`' `enrich_company` tool calls.

Plain scalar arguments, not a `colt_integrations.enrichment.CompanyCandidate` — see
`DiscoverCompany`'s docstring for why.

"Must not silently overwrite high-confidence data with lower-confidence provider data. Use
source precedence and confidence rules." This milestone's confidence rule is deliberately
record-level, not field-level: a `Company`'s `source_metadata.confidence` is the confidence of
whatever provider last enriched the whole record, and a new candidate only overwrites the
record's enrichable fields when its own confidence is at least that high — a documented
simplification (a future milestone could track confidence per field instead), not a silent gap.
A lower-confidence candidate is a no-op: the existing record is returned unchanged, never
degraded.
"""

from __future__ import annotations

from uuid import UUID

from colt_application.identity import normalize_domain, normalize_linkedin_url
from colt_application.ports.company_repository import CompanyRepository
from colt_domain import Company


class EnrichCompany:
    def __init__(self, companies: CompanyRepository) -> None:
        self._companies = companies

    async def __call__(
        self,
        company_id: UUID,
        *,
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
    ) -> Company:
        existing = await self._companies.get(company_id)
        if existing is None:
            raise ValueError(f"No company {company_id} to enrich.")

        stored_confidence = float(existing.source_metadata.get("confidence", 0.0))
        if confidence < stored_confidence:
            return existing

        return await self._companies.update(
            company_id,
            domain=domain,
            normalized_domain=normalize_domain(domain) if domain is not None else None,
            industry=industry,
            employee_count=employee_count,
            country=country,
            region=region,
            city=city,
            website_url=website_url,
            linkedin_url=normalize_linkedin_url(linkedin_url) if linkedin_url is not None else None,
            source_metadata={
                "provider": provider,
                "provider_id": provider_id,
                "confidence": confidence,
            },
        )
