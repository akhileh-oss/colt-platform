"""`OpportunityAgent` (CLAUDE.md §12.11) — the full decision loop through `AgentRuntime`,
hermetically: in-memory `OpportunityRepository`, and a real `AsyncAnthropic` instance with only
`.messages.create` replaced (the same pattern every prior milestone's own tests establish).
`tests/integration/test_opportunity_engine.py` separately proves the same mechanism against
real Postgres, proving Milestone 21's acceptance criterion literally.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr, ValidationError

from colt_agents.opportunity_agent import (
    OPPORTUNITY_AGENT_DEFINITION,
    OpportunityAgentInput,
    OpportunityDecision,
)
from colt_agents.registry import ToolRegistry
from colt_agents.runtime import AgentRuntime
from colt_agents.tools import build_create_or_update_opportunity_tool
from colt_ai import AnthropicGateway
from colt_application.use_cases.create_or_update_opportunity import CreateOrUpdateOpportunity
from colt_config import AnthropicSettings
from colt_domain import AgentRun, Opportunity, PipelineStage, ToolCall

NOW = datetime.now(UTC)


class FakeOpportunityRepository:
    def __init__(self) -> None:
        self._by_id: dict[UUID, Opportunity] = {}
        self.added: list[Opportunity] = []

    async def add(
        self,
        *,
        company_id: UUID,
        primary_person_id: UUID | None = None,
        lead_id: UUID | None = None,
        pipeline_stage: PipelineStage = PipelineStage.QUALIFIED,
        estimated_value: float | None = None,
        currency: str | None = None,
        probability: float | None = None,
        owner_id: UUID | None = None,
        source: str | None = None,
        is_estimated_value: bool = False,
    ) -> Opportunity:
        opportunity = Opportunity(
            id=uuid4(),
            organization_id=uuid4(),
            company_id=company_id,
            primary_person_id=primary_person_id,
            lead_id=lead_id,
            pipeline_stage=pipeline_stage,
            estimated_value=estimated_value,
            currency=currency,
            probability=probability,
            owner_id=owner_id,
            source=source,
            is_estimated_value=is_estimated_value,
            created_at=NOW,
            updated_at=NOW,
        )
        self._by_id[opportunity.id] = opportunity
        self.added.append(opportunity)
        return opportunity

    async def get(self, opportunity_id: UUID) -> Opportunity | None:
        return self._by_id.get(opportunity_id)

    async def get_open_by_company(self, company_id: UUID) -> Opportunity | None:
        open_stages = frozenset(PipelineStage) - {PipelineStage.WON, PipelineStage.LOST}
        for opportunity in self._by_id.values():
            if opportunity.company_id == company_id and opportunity.pipeline_stage in open_stages:
                return opportunity
        return None

    async def list_all(self) -> list[Opportunity]:
        return list(self._by_id.values())

    async def update_stage(self, *args: Any, **kwargs: Any) -> Opportunity:
        raise NotImplementedError

    async def assign_owner(self, *args: Any, **kwargs: Any) -> Opportunity:
        raise NotImplementedError

    async def update_value(self, *args: Any, **kwargs: Any) -> Opportunity:
        raise NotImplementedError


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


def _input(company_id: UUID) -> OpportunityAgentInput:
    return OpportunityAgentInput(
        conversation_id=uuid4(),
        company_id=company_id,
        company_name="Acme Rockets",
        person_name="Jane Doe",
        lead_id=uuid4(),
        primary_person_id=uuid4(),
        subject="Re: hello",
        body="We have about $50k budgeted for this and want to move forward next week.",
    )


async def test_commercial_intent_creates_an_opportunity_via_the_tool() -> None:
    repo = FakeOpportunityRepository()
    registry = ToolRegistry()
    registry.register(build_create_or_update_opportunity_tool(CreateOrUpdateOpportunity(repo)))
    company_id = uuid4()

    turn = 0

    async def fake_create(**kwargs: Any) -> Message:
        nonlocal turn
        turn += 1
        if turn == 1:
            return Message(
                id="msg_1",
                content=[
                    ToolUseBlock(
                        id="toolu_1",
                        input={
                            "company_id": str(company_id),
                            "estimated_value": 50000.0,
                            "currency": "USD",
                            "is_estimate": True,
                        },
                        name="create_or_update_opportunity",
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
        output = OpportunityDecision(
            has_commercial_intent=True,
            estimated_value=50000.0,
            currency="USD",
            is_estimate=True,
        )
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

    agent_runs = FakeAgentRunRepository()
    tool_calls = FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    output = await runtime.run(OPPORTUNITY_AGENT_DEFINITION, input=_input(company_id))

    assert isinstance(output, OpportunityDecision)
    assert output.has_commercial_intent is True
    assert len(repo.added) == 1
    assert repo.added[0].company_id == company_id
    assert repo.added[0].estimated_value == 50000.0
    assert repo.added[0].is_estimated_value is True


async def test_no_commercial_intent_never_calls_the_tool() -> None:
    repo = FakeOpportunityRepository()
    registry = ToolRegistry()
    registry.register(build_create_or_update_opportunity_tool(CreateOrUpdateOpportunity(repo)))
    company_id = uuid4()

    async def fake_create(**kwargs: Any) -> Message:
        output = OpportunityDecision(has_commercial_intent=False)
        return Message(
            id="msg_1",
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

    output = await runtime.run(OPPORTUNITY_AGENT_DEFINITION, input=_input(company_id))

    assert isinstance(output, OpportunityDecision)
    assert output.has_commercial_intent is False
    assert repo.added == []


def test_an_estimated_value_without_is_estimate_is_rejected() -> None:
    with pytest.raises(ValidationError, match="is_estimate"):
        OpportunityDecision(has_commercial_intent=True, estimated_value=1000.0, currency="USD")


def test_an_estimated_value_without_currency_is_rejected() -> None:
    with pytest.raises(ValidationError, match="currency"):
        OpportunityDecision(has_commercial_intent=True, estimated_value=1000.0, is_estimate=True)
