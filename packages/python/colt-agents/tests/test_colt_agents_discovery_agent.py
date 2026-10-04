"""`DiscoveryAgent` (CLAUDE.md §12.3) — the full search_companies -> search_people loop through
`AgentRuntime`, hermetically: a `FakeEnrichmentProvider` and in-memory `CompanyRepository`/
`PersonRepository`, and a real `AsyncAnthropic` instance with only `.messages.create` replaced
(the same pattern Milestone 08/09/10's own tests establish).
`tests/integration/test_discovery_agent.py` separately proves the same mechanism against real
Postgres, proving Milestone 11's acceptance criterion literally.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr

from colt_agents.discovery_agent import (
    DISCOVERY_AGENT_DEFINITION,
    DiscoveredCompany,
    DiscoveredPerson,
    DiscoveryAgentInput,
    DiscoveryAgentOutput,
)
from colt_agents.registry import ToolRegistry
from colt_agents.runtime import AgentRuntime
from colt_agents.tools import (
    build_search_companies_tool,
    build_search_people_tool,
    build_search_web_tool,
)
from colt_ai import AnthropicGateway
from colt_application.use_cases.discover_company import DiscoverCompany
from colt_application.use_cases.discover_person import DiscoverPerson
from colt_config import AnthropicSettings
from colt_domain import AgentRun, Company, Person, ToolCall
from colt_integrations.enrichment.fake import FakeEnrichmentProvider
from colt_integrations.enrichment.port import CompanyCandidate, PersonCandidate
from colt_integrations.search.fake import FakeSearchProvider


class FakeCompanyRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Company] = {}

    async def add(self, **kwargs: Any) -> Company:
        company = Company(
            id=uuid4(),
            organization_id=uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            **kwargs,
        )
        self.rows[company.id] = company
        return company

    async def get(self, company_id: UUID) -> Company | None:
        return self.rows.get(company_id)

    async def find_by_normalized_domain(self, normalized_domain: str) -> Company | None:
        return next(
            (c for c in self.rows.values() if c.normalized_domain == normalized_domain), None
        )

    async def find_by_linkedin_url(self, linkedin_url: str) -> Company | None:
        return next((c for c in self.rows.values() if c.linkedin_url == linkedin_url), None)

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Company | None:
        return next(
            (
                c
                for c in self.rows.values()
                if c.source_metadata.get("provider") == provider
                and c.source_metadata.get("provider_id") == provider_id
            ),
            None,
        )

    async def update(self, company_id: UUID, **fields: Any) -> Company:
        existing = self.rows[company_id]
        updated = existing.model_copy(update={k: v for k, v in fields.items() if v is not None})
        self.rows[company_id] = updated
        return updated


class FakePersonRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Person] = {}

    async def add(self, **kwargs: Any) -> Person:
        person = Person(
            id=uuid4(),
            organization_id=uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            **kwargs,
        )
        self.rows[person.id] = person
        return person

    async def get(self, person_id: UUID) -> Person | None:
        return self.rows.get(person_id)

    async def find_by_email(self, email: str) -> Person | None:
        return next((p for p in self.rows.values() if p.email == email), None)

    async def find_by_linkedin_url(self, linkedin_url: str) -> Person | None:
        return next((p for p in self.rows.values() if p.linkedin_url == linkedin_url), None)

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Person | None:
        return next(
            (
                p
                for p in self.rows.values()
                if p.source_metadata.get("provider") == provider
                and p.source_metadata.get("provider_id") == provider_id
            ),
            None,
        )

    async def list_by_company(self, company_id: UUID) -> list[Person]:
        return [p for p in self.rows.values() if p.company_id == company_id]

    async def update(self, person_id: UUID, **fields: Any) -> Person:
        existing = self.rows[person_id]
        updated = existing.model_copy(update={k: v for k, v in fields.items() if v is not None})
        self.rows[person_id] = updated
        return updated


class FakeAgentRunRepository:
    def __init__(self) -> None:
        self.organization_id = uuid4()
        self.runs: dict[UUID, AgentRun] = {}

    async def start(self, **kwargs: Any) -> AgentRun:
        run = AgentRun(
            id=uuid4(), organization_id=self.organization_id, started_at=datetime.now(UTC), **kwargs
        )
        self.runs[run.id] = run
        return run

    async def complete(self, run_id: UUID, **kwargs: Any) -> AgentRun:
        self.runs[run_id] = self.runs[run_id].completed(**kwargs)
        return self.runs[run_id]

    async def fail(self, run_id: UUID, **kwargs: Any) -> AgentRun:
        self.runs[run_id] = self.runs[run_id].failed(**kwargs)
        return self.runs[run_id]


class FakeToolCallRepository:
    def __init__(self, organization_id: UUID) -> None:
        self.organization_id = organization_id
        self.calls: dict[UUID, ToolCall] = {}

    async def start(self, **kwargs: Any) -> ToolCall:
        call = ToolCall(
            id=uuid4(), organization_id=self.organization_id, started_at=datetime.now(UTC), **kwargs
        )
        self.calls[call.id] = call
        return call

    async def succeed(self, tool_call_id: UUID, **kwargs: Any) -> ToolCall:
        self.calls[tool_call_id] = self.calls[tool_call_id].succeeded(**kwargs)
        return self.calls[tool_call_id]

    async def fail(self, tool_call_id: UUID, **kwargs: Any) -> ToolCall:
        self.calls[tool_call_id] = self.calls[tool_call_id].failed(**kwargs)
        return self.calls[tool_call_id]


def _usage(input_tokens: int = 10, output_tokens: int = 5) -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def _gateway(fake_create: Any) -> AnthropicGateway:
    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    client.messages.create = fake_create  # type: ignore[method-assign]
    return AnthropicGateway(
        AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )


async def test_discovery_agent_produces_deduplicated_records_with_source_metadata() -> None:
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
        },
        person_search_results={
            "VP Engineering": [
                PersonCandidate(
                    full_name="Jane Doe",
                    provider="apollo",
                    confidence=0.9,
                    provider_id="person_1",
                    title="VP Engineering",
                )
            ]
        },
    )
    companies = FakeCompanyRepository()
    people = FakePersonRepository()
    registry = ToolRegistry()
    registry.register(build_search_companies_tool(provider, DiscoverCompany(companies)))
    registry.register(build_search_people_tool(provider, DiscoverPerson(people)))
    registry.register(build_search_web_tool(FakeSearchProvider()))

    discovered_company_id: UUID | None = None
    turn = 0

    async def fake_create(**kwargs: Any) -> Message:
        nonlocal turn, discovered_company_id
        turn += 1
        if turn == 1:
            return Message(
                id="msg_1",
                content=[
                    ToolUseBlock(
                        id="toolu_1",
                        input={"query": "rocket companies", "max_results": 5},
                        name="search_companies",
                        type="tool_use",
                    )
                ],
                model=kwargs["model"],
                role="assistant",
                stop_reason="tool_use",
                stop_sequence=None,
                type="message",
                usage=_usage(),
            )
        if turn == 2:
            last_tool_result = kwargs["messages"][-1]["content"][0]
            discovered_company_id = UUID(
                json.loads(last_tool_result["content"])["results"][0]["company_id"]
            )
            return Message(
                id="msg_2",
                content=[
                    ToolUseBlock(
                        id="toolu_2",
                        input={
                            "company_id": str(discovered_company_id),
                            "query": "VP Engineering",
                            "max_results": 5,
                        },
                        name="search_people",
                        type="tool_use",
                    )
                ],
                model=kwargs["model"],
                role="assistant",
                stop_reason="tool_use",
                stop_sequence=None,
                type="message",
                usage=_usage(),
            )
        assert discovered_company_id is not None
        output = DiscoveryAgentOutput(
            companies=[
                DiscoveredCompany(
                    company_id=discovered_company_id,
                    name="Acme Rockets",
                    domain="acme.example",
                    provider="apollo",
                    confidence=0.9,
                )
            ],
            people=[
                DiscoveredPerson(
                    person_id=next(iter(people.rows.values())).id,
                    full_name="Jane Doe",
                    title="VP Engineering",
                    provider="apollo",
                    confidence=0.9,
                )
            ],
        )
        return Message(
            id="msg_3",
            content=[TextBlock(text=output.model_dump_json(), type="text")],
            model=kwargs["model"],
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage=_usage(),
        )

    agent_runs = FakeAgentRunRepository()
    tool_calls = FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    raw_output = await runtime.run(
        DISCOVERY_AGENT_DEFINITION, input=DiscoveryAgentInput(icp_description="rocket companies")
    )
    assert isinstance(raw_output, DiscoveryAgentOutput)
    output = raw_output

    assert len(companies.rows) == 1
    assert len(people.rows) == 1
    (company,) = companies.rows.values()
    (person,) = people.rows.values()
    assert company.source_metadata == {
        "provider": "apollo",
        "provider_id": "org_1",
        "confidence": 0.9,
    }
    assert person.source_metadata["provider"] == "apollo"
    assert output.companies[0].company_id == company.id
    assert output.people[0].person_id == person.id

    # Re-running search_companies/search_people with the same provider ids must not duplicate
    # rows (CLAUDE.md §22) - call the use cases directly to prove this without a second full
    # agent run.
    _, created = await DiscoverCompany(companies)(
        name="Acme Rockets", provider="apollo", confidence=0.9, provider_id="org_1"
    )
    assert created is False
    assert len(companies.rows) == 1
