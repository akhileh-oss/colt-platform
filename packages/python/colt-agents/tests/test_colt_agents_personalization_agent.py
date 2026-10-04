"""`PersonalizationAgent` (CLAUDE.md §12.8) — the full list_evidence_for_lead → select_evidence
loop through `AgentRuntime`, hermetically: in-memory `EvidenceRepository`/`LeadRepository`, and
a real `AsyncAnthropic` instance with only `.messages.create` replaced (the same pattern every
prior milestone's own tests establish). `tests/integration/test_personalization_and_messaging.py`
separately proves the same mechanism against real Postgres.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message as AnthropicMessage
from anthropic.types import TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr

from colt_agents.personalization_agent import (
    PERSONALIZATION_AGENT_DEFINITION,
    PersonalizationAgentInput,
    PersonalizationStrategy,
)
from colt_agents.registry import ToolRegistry
from colt_agents.runtime import AgentRuntime
from colt_agents.tools import build_list_evidence_for_lead_tool, build_select_evidence_tool
from colt_ai import AnthropicGateway
from colt_application.use_cases.list_evidence_for_lead import ListEvidenceForLead
from colt_application.use_cases.select_personalization_evidence import (
    SelectPersonalizationEvidence,
)
from colt_config import AnthropicSettings
from colt_domain import AgentRun, Evidence, Lead, ToolCall

NOW = datetime.now(UTC)


class FakeLeadRepository:
    def __init__(self, lead: Lead) -> None:
        self.lead = lead

    async def get(self, lead_id: UUID) -> Lead | None:
        return self.lead if lead_id == self.lead.id else None

    async def update_status(self, lead_id: UUID, status: object, *, at: datetime) -> Lead:
        raise NotImplementedError


class FakeEvidenceRepository:
    def __init__(self, evidence: list[Evidence]) -> None:
        self._evidence = evidence

    async def add(self, **kwargs: object) -> Evidence:
        raise NotImplementedError

    async def get(self, evidence_id: UUID) -> Evidence | None:
        return next((e for e in self._evidence if e.id == evidence_id), None)

    async def list_by_entity(self, entity_type: str, entity_id: UUID) -> list[Evidence]:
        return [
            e for e in self._evidence if e.entity_type == entity_type and e.entity_id == entity_id
        ]


class FakeAgentRunRepository:
    def __init__(self) -> None:
        self.organization_id = uuid4()
        self.runs: dict[UUID, AgentRun] = {}

    async def start(self, **kwargs: Any) -> AgentRun:
        run = AgentRun(id=uuid4(), organization_id=self.organization_id, started_at=NOW, **kwargs)
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
        call = ToolCall(id=uuid4(), organization_id=self.organization_id, started_at=NOW, **kwargs)
        self.calls[call.id] = call
        return call

    async def succeed(self, tool_call_id: UUID, **kwargs: Any) -> ToolCall:
        self.calls[tool_call_id] = self.calls[tool_call_id].succeeded(**kwargs)
        return self.calls[tool_call_id]

    async def fail(self, tool_call_id: UUID, **kwargs: Any) -> ToolCall:
        self.calls[tool_call_id] = self.calls[tool_call_id].failed(**kwargs)
        return self.calls[tool_call_id]


def _usage() -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
    )


def _gateway(fake_create: Any) -> AnthropicGateway:
    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    client.messages.create = fake_create  # type: ignore[method-assign]
    return AnthropicGateway(
        AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )


@pytest.mark.asyncio
async def test_personalization_agent_selects_evidence_and_forms_a_strategy() -> None:
    company_id, person_id = uuid4(), uuid4()
    lead = Lead(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=company_id,
        person_id=person_id,
        created_at=NOW,
        updated_at=NOW,
    )
    evidence = Evidence(
        id=uuid4(),
        organization_id=uuid4(),
        entity_type="Company",
        entity_id=company_id,
        claim="They raised a $20M Series B.",
        source_url="https://example.com/news",
        observed_at=NOW,
        created_at=NOW,
    )

    leads = FakeLeadRepository(lead)
    evidence_repo = FakeEvidenceRepository([evidence])
    registry = ToolRegistry()
    registry.register(build_list_evidence_for_lead_tool(ListEvidenceForLead(leads, evidence_repo)))
    registry.register(build_select_evidence_tool(SelectPersonalizationEvidence(evidence_repo)))

    turn = 0

    async def fake_create(**kwargs: Any) -> AnthropicMessage:
        nonlocal turn
        turn += 1
        if turn == 1:
            return AnthropicMessage(
                id="msg_1",
                content=[
                    ToolUseBlock(
                        id="toolu_1",
                        input={"lead_id": str(lead.id)},
                        name="list_evidence_for_lead",
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
            return AnthropicMessage(
                id="msg_2",
                content=[
                    ToolUseBlock(
                        id="toolu_2",
                        input={"evidence_ids": [str(evidence.id)]},
                        name="select_evidence",
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
        last_tool_result = kwargs["messages"][-1]["content"][0]
        result = json.loads(last_tool_result["content"])
        output = PersonalizationStrategy(
            lead_id=lead.id,
            evidence_ids=[UUID(v) for v in result["verified_evidence_ids"]],
            angle="Open with the Series B and ask how they're scaling the team.",
            business_relevance="Fresh funding usually means headcount growth in the next quarter.",
        )
        return AnthropicMessage(
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

    output = await runtime.run(
        PERSONALIZATION_AGENT_DEFINITION,
        input=PersonalizationAgentInput(
            lead_id=lead.id, company_name="Acme Rockets", person_name="Jane Doe"
        ),
    )

    assert isinstance(output, PersonalizationStrategy)
    assert output.evidence_ids == [evidence.id]
