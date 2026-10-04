"""`search_people` (CLAUDE.md §12.3's Data category) — scoped to an already-discovered company,
since a `Person` row requires a `company_id` (§10.4). "Output must include source/provider
identifiers."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.use_cases.discover_person import DiscoverPerson
from colt_integrations.enrichment.port import EnrichmentProvider

TOOL_NAME = "search_people"
TOOL_VERSION = "v1"


class SearchPeopleInput(BaseModel):
    company_id: UUID
    query: str
    max_results: int = 10


class SearchPeopleResultItem(BaseModel):
    person_id: UUID
    full_name: str
    title: str | None
    provider: str
    confidence: float
    newly_discovered: bool


class SearchPeopleOutput(BaseModel):
    results: list[SearchPeopleResultItem]


def build_search_people_tool(provider: EnrichmentProvider, discover_person: DiscoverPerson) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, SearchPeopleInput)  # noqa: S101 - guards an
        # internal contract this tool's own `input_model` guarantees; never reachable with
        # real input.
        candidates = await provider.search_people(
            validated_input.query, max_results=validated_input.max_results
        )
        items = []
        for candidate in candidates:
            person, created = await discover_person(
                company_id=validated_input.company_id,
                full_name=candidate.full_name,
                provider=candidate.provider,
                confidence=candidate.confidence,
                provider_id=candidate.provider_id,
                first_name=candidate.first_name,
                last_name=candidate.last_name,
                title=candidate.title,
                email=candidate.email,
                linkedin_url=candidate.linkedin_url,
            )
            items.append(
                SearchPeopleResultItem(
                    person_id=person.id,
                    full_name=person.full_name,
                    title=person.title,
                    provider=candidate.provider,
                    confidence=candidate.confidence,
                    newly_discovered=created,
                )
            )
        return SearchPeopleOutput(results=items)

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Search for candidate people at a given company matching a query. Each result is "
            "deduplicated against already-known people (CLAUDE.md §22) and carries its source "
            "provider and confidence."
        ),
        input_model=SearchPeopleInput,
        handler=handler,
    )
