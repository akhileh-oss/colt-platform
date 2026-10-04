"""`search_companies` (CLAUDE.md §12.3's Data category) — "Output must include source/provider
identifiers."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.use_cases.discover_company import DiscoverCompany
from colt_integrations.enrichment.port import EnrichmentProvider

TOOL_NAME = "search_companies"
TOOL_VERSION = "v1"


class SearchCompaniesInput(BaseModel):
    query: str
    max_results: int = 10


class SearchCompaniesResultItem(BaseModel):
    company_id: UUID
    name: str
    domain: str | None
    provider: str
    confidence: float
    newly_discovered: bool


class SearchCompaniesOutput(BaseModel):
    results: list[SearchCompaniesResultItem]


def build_search_companies_tool(
    provider: EnrichmentProvider, discover_company: DiscoverCompany
) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, SearchCompaniesInput)  # noqa: S101 - guards an
        # internal contract this tool's own `input_model` guarantees; never reachable with
        # real input.
        candidates = await provider.search_companies(
            validated_input.query, max_results=validated_input.max_results
        )
        items = []
        for candidate in candidates:
            company, created = await discover_company(
                name=candidate.name,
                provider=candidate.provider,
                confidence=candidate.confidence,
                provider_id=candidate.provider_id,
                domain=candidate.domain,
                industry=candidate.industry,
                employee_count=candidate.employee_count,
                country=candidate.country,
                region=candidate.region,
                city=candidate.city,
                website_url=candidate.website_url,
                linkedin_url=candidate.linkedin_url,
            )
            items.append(
                SearchCompaniesResultItem(
                    company_id=company.id,
                    name=company.name,
                    domain=company.domain,
                    provider=candidate.provider,
                    confidence=candidate.confidence,
                    newly_discovered=created,
                )
            )
        return SearchCompaniesOutput(results=items)

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Search for candidate companies matching a query. Each result is deduplicated "
            "against already-known companies (CLAUDE.md §22) and carries its source provider "
            "and confidence."
        ),
        input_model=SearchCompaniesInput,
        handler=handler,
    )
