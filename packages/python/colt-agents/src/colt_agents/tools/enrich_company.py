"""`enrich_company` (CLAUDE.md §12.4's Data category)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.use_cases.enrich_company import EnrichCompany
from colt_integrations.enrichment.port import EnrichmentProvider

TOOL_NAME = "enrich_company"
TOOL_VERSION = "v1"


class EnrichCompanyInput(BaseModel):
    company_id: UUID
    domain: str


class EnrichCompanyOutput(BaseModel):
    company_id: UUID
    industry: str | None
    employee_count: int | None
    country: str | None


def build_enrich_company_tool(provider: EnrichmentProvider, enrich_company: EnrichCompany) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, EnrichCompanyInput)  # noqa: S101 - guards an
        # internal contract this tool's own `input_model` guarantees; never reachable with
        # real input.
        candidate = await provider.enrich_company(validated_input.domain)
        if candidate is None:
            company = await enrich_company(
                validated_input.company_id, provider="none", confidence=0.0
            )
        else:
            company = await enrich_company(
                validated_input.company_id,
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
        return EnrichCompanyOutput(
            company_id=company.id,
            industry=company.industry,
            employee_count=company.employee_count,
            country=company.country,
        )

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Enrich a known company by domain. Never silently overwrites higher-confidence "
            "data with a lower-confidence result (CLAUDE.md §12.4)."
        ),
        input_model=EnrichCompanyInput,
        handler=handler,
    )
