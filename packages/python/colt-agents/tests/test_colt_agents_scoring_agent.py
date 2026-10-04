"""`ScoringAgent` (CLAUDE.md §12.7, §21) — the full score_lead loop through `AgentRuntime`,
hermetically: in-memory `LeadScoreRepository`/`LeadRepository`, and a real `AsyncAnthropic`
instance with only `.messages.create` replaced (the same pattern Milestone 08/09/10/11/12's own
tests establish). `tests/integration/test_scoring_agent.py` separately proves the same
mechanism against real Postgres, proving Milestone 13's acceptance criterion literally.
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

from colt_agents.registry import ToolRegistry
from colt_agents.runtime import AgentRuntime
from colt_agents.scoring_agent import (
    SCORING_AGENT_DEFINITION,
    ScoringAgentInput,
    ScoringAgentOutput,
)
from colt_agents.tools import build_score_lead_tool
from colt_ai import AnthropicGateway
from colt_application.scoring import compute_overall_score, determine_reason_codes
from colt_application.use_cases.score_lead import ScoreLead
from colt_config import AnthropicSettings
from colt_domain import AgentRun, Lead, LeadScore, LeadStatus, ToolCall


class FakeLeadScoreRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, LeadScore] = {}

    async def add(self, **kwargs: Any) -> LeadScore:
        score = LeadScore(
            id=uuid4(), organization_id=uuid4(), created_at=datetime.now(UTC), **kwargs
        )
        self.rows[score.id] = score
        return score

    async def get(self, lead_score_id: UUID) -> LeadScore | None:
        return self.rows.get(lead_score_id)

    async def list_by_lead(self, lead_id: UUID) -> list[LeadScore]:
        return [s for s in self.rows.values() if s.lead_id == lead_id]


class FakeLeadRepository:
    def __init__(self, lead: Lead) -> None:
        self.lead = lead

    async def get(self, lead_id: UUID) -> Lead | None:
        return self.lead if lead_id == self.lead.id else None

    async def update_status(self, lead_id: UUID, status: LeadStatus, *, at: datetime) -> Lead:
        self.lead = self.lead.with_status(status, at=at)
        return self.lead


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


async def test_scoring_agent_computes_a_reproducible_overall_score_and_qualifies_the_lead() -> None:
    lead = Lead(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        person_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    lead_scores = FakeLeadScoreRepository()
    leads = FakeLeadRepository(lead)
    registry = ToolRegistry()
    registry.register(build_score_lead_tool(ScoreLead(lead_scores, leads)))

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
                            "lead_id": str(lead.id),
                            "icp_fit": 0.9,
                            "persona_fit": 0.9,
                            "signal_strength": 0.9,
                            "timing": 0.9,
                            "model_assessment": 0.9,
                        },
                        name="score_lead",
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
        output = ScoringAgentOutput(
            lead_score_id=UUID(result["lead_score_id"]),
            persona_fit=0.9,
            model_assessment=0.9,
            overall_score=result["overall_score"],
            reason_codes=result["reason_codes"],
            qualified=result["qualified"],
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

    output = await runtime.run(
        SCORING_AGENT_DEFINITION,
        input=ScoringAgentInput(lead_id=lead.id, icp_fit=0.9, signal_strength=0.9, timing=0.9),
    )

    assert isinstance(output, ScoringAgentOutput)
    assert output.qualified is True
    assert leads.lead.status == LeadStatus.QUALIFIED

    (score,) = lead_scores.rows.values()
    expected_overall = compute_overall_score(
        icp_fit=0.9, persona_fit=0.9, signal_strength=0.9, timing=0.9, model_assessment=0.9
    )
    expected_codes = determine_reason_codes(
        icp_fit=0.9,
        persona_fit=0.9,
        signal_strength=0.9,
        timing=0.9,
        overall_score=expected_overall,
    )
    assert score.overall_score == expected_overall
    assert output.overall_score == expected_overall
    assert output.reason_codes == expected_codes
