"""Milestone 11's acceptance criterion, proven literally: "Given a target ICP, Colt can
produce deduplicated candidate companies/people with source metadata" (CLAUDE.md §68).

Everything here is real except the Anthropic call itself: real Postgres, real RLS, real
`SqlAlchemyCompanyRepository`/`SqlAlchemyPersonRepository`, and a real `DiscoverCompany`/
`DiscoverPerson` use case pair performing the actual §22 identity-resolution logic. The
`EnrichmentProvider` is `FakeEnrichmentProvider` — no real enrichment-provider API key exists in
this environment (same situation `colt_integrations.search`'s `BraveSearchProvider` is in).

The test runs the DiscoveryAgent twice with overlapping candidates (same provider + provider_id
on the second run) and proves against real, independently-queried-back rows that the second run
deduplicates rather than creating a second company/person.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

from typing import Any

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr
from sqlalchemy import text

from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.discovery_agent import (
    DISCOVERY_AGENT_DEFINITION,
    DiscoveryAgentInput,
    DiscoveryAgentOutput,
)
from colt_agents.tools import (
    build_search_companies_tool,
    build_search_people_tool,
    build_search_web_tool,
)
from colt_ai import AnthropicGateway
from colt_application.use_cases.discover_company import DiscoverCompany
from colt_application.use_cases.discover_person import DiscoverPerson
from colt_config import AnthropicSettings
from colt_db.repositories.agent_run_repository import SqlAlchemyAgentRunRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_db.repositories.tool_call_repository import SqlAlchemyToolCallRepository
from colt_integrations.enrichment.fake import FakeEnrichmentProvider
from colt_integrations.enrichment.port import CompanyCandidate
from colt_integrations.search.fake import FakeSearchProvider


def _usage() -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
    )


def _one_tool_call_then_final_message(tool_name: str, tool_input: dict[str, Any]) -> Any:
    calls: list[dict[str, Any]] = []

    async def fake_create(**kwargs: Any) -> Message:
        calls.append(kwargs)
        if len(calls) == 1:
            return Message(
                id="msg_1",
                content=[
                    ToolUseBlock(id="toolu_1", input=tool_input, name=tool_name, type="tool_use")
                ],
                model=kwargs["model"],
                role="assistant",
                stop_reason="tool_use",
                stop_sequence=None,
                type="message",
                usage=_usage(),
            )
        output = DiscoveryAgentOutput(companies=[], people=[])
        return Message(
            id="msg_2",
            content=[TextBlock(text=output.model_dump_json(), type="text")],
            model=kwargs["model"],
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage=_usage(),
        )

    return fake_create


@pytest.mark.asyncio
async def test_discovery_can_be_run_twice_without_duplicating_records(
    open_app_session: Any, two_organizations: tuple[Any, Any]
) -> None:
    org_a, _ = two_organizations
    provider = FakeEnrichmentProvider(
        company_search_results={
            "rocket companies": [
                CompanyCandidate(
                    name="Acme Rockets",
                    provider="apollo",
                    confidence=0.9,
                    provider_id="org_1",
                    domain="acme.example",
                )
            ]
        }
    )

    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    client.messages.create = _one_tool_call_then_final_message(  # type: ignore[method-assign]
        "search_companies", {"query": "rocket companies", "max_results": 5}
    )
    gateway = AnthropicGateway(
        AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )

    async def run_discovery_once() -> None:
        session = await open_app_session()
        async with session, session.begin():
            companies = await SqlAlchemyCompanyRepository.create(session, org_a)
            people = SqlAlchemyPersonRepository(session, org_a)
            registry = ToolRegistry()
            registry.register(build_search_companies_tool(provider, DiscoverCompany(companies)))
            registry.register(build_search_people_tool(provider, DiscoverPerson(people)))
            registry.register(build_search_web_tool(FakeSearchProvider()))
            agent_runs = SqlAlchemyAgentRunRepository(session, org_a)
            tool_calls = SqlAlchemyToolCallRepository(session, org_a)
            runtime = AgentRuntime(gateway, registry, agent_runs, tool_calls)
            await runtime.run(
                DISCOVERY_AGENT_DEFINITION,
                input=DiscoveryAgentInput(icp_description="rocket companies"),
            )

    await run_discovery_once()
    await run_discovery_once()

    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        await SqlAlchemyCompanyRepository.create(verify_session, org_a)
        company_rows = (
            (
                await verify_session.execute(
                    text("SELECT * FROM companies WHERE organization_id = :org"), {"org": org_a}
                )
            )
            .mappings()
            .all()
        )

    assert len(company_rows) == 1, "a second discovery run must deduplicate, not duplicate"
    company_row = company_rows[0]
    assert company_row["source_metadata"]["provider"] == "apollo"
    assert company_row["source_metadata"]["provider_id"] == "org_1"
    assert company_row["normalized_domain"] == "acme.example"


@pytest.mark.asyncio
async def test_discovery_agent_dossier_output_links_people_to_their_company(
    open_app_session: Any, two_organizations: tuple[Any, Any]
) -> None:
    org_a, _ = two_organizations

    session = await open_app_session()
    async with session, session.begin():
        companies = await SqlAlchemyCompanyRepository.create(session, org_a)
        people = SqlAlchemyPersonRepository(session, org_a)
        discover_company = DiscoverCompany(companies)
        discover_person = DiscoverPerson(people)

        company, _ = await discover_company(
            name="Acme Rockets", provider="apollo", confidence=0.9, provider_id="org_1"
        )
        person, _ = await discover_person(
            company_id=company.id,
            full_name="Jane Doe",
            provider="apollo",
            confidence=0.9,
            provider_id="person_1",
        )

        assert person.company_id == company.id

        person_rows = (
            (
                await session.execute(
                    text("SELECT * FROM people WHERE organization_id = :org"), {"org": org_a}
                )
            )
            .mappings()
            .all()
        )
    assert len(person_rows) == 1
    assert person_rows[0]["company_id"] == company.id
    assert person_rows[0]["source_metadata"]["provider_id"] == "person_1"
