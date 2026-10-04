"""`SignalAgent` (CLAUDE.md §12.6) — the full poll_signal_sources -> record_signal loop through
`AgentRuntime`, hermetically: a `FakeSignalTriggerSource` and an in-memory `SignalRepository`,
and a real `AsyncAnthropic` instance with only `.messages.create` replaced (the same pattern
Milestone 08/09/10/11's own tests establish). `tests/integration/test_signal_agent.py`
separately proves the same mechanism against real Postgres, proving Milestone 12's acceptance
criterion literally.
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
from colt_agents.signal_agent import SIGNAL_AGENT_DEFINITION, SignalAgentInput, SignalAgentOutput
from colt_agents.tools import build_poll_signal_sources_tool, build_record_signal_tool
from colt_ai import AnthropicGateway
from colt_application.signals import rank_signal
from colt_application.use_cases.record_signal import RecordSignal
from colt_config import AnthropicSettings
from colt_domain import AgentRun, Signal, ToolCall
from colt_integrations.signals.fake import FakeSignalTriggerSource
from colt_integrations.signals.port import SignalTriggerPayload


class FakeSignalRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Signal] = {}

    async def add(self, **kwargs: Any) -> Signal:
        kwargs["raw_payload"] = kwargs.get("raw_payload") or {}
        signal = Signal(id=uuid4(), organization_id=uuid4(), created_at=datetime.now(UTC), **kwargs)
        self.rows[signal.id] = signal
        return signal

    async def get(self, signal_id: UUID) -> Signal | None:
        return self.rows.get(signal_id)


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


async def test_signal_agent_polls_and_records_the_strongest_signal_with_a_correct_rank() -> None:
    company_id = uuid4()
    trigger_source = FakeSignalTriggerSource(
        [
            SignalTriggerPayload(
                company_id=company_id,
                source="mock-newswire",
                observed_at=datetime.now(UTC),
                source_url="https://news.example.com/acme-series-b",
                source_type="news",
                raw_payload={"headline": "Acme Rockets raises $20M Series B"},
            )
        ]
    )
    signals = FakeSignalRepository()
    registry = ToolRegistry()
    registry.register(build_poll_signal_sources_tool(trigger_source))
    registry.register(build_record_signal_tool(RecordSignal(signals)))

    recorded_signal_id: UUID | None = None
    recorded_rank: float | None = None
    turn = 0

    async def fake_create(**kwargs: Any) -> Message:
        nonlocal turn, recorded_signal_id, recorded_rank
        turn += 1
        if turn == 1:
            return Message(
                id="msg_1",
                content=[
                    ToolUseBlock(
                        id="toolu_1", input={}, name="poll_signal_sources", type="tool_use"
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
            return Message(
                id="msg_2",
                content=[
                    ToolUseBlock(
                        id="toolu_2",
                        input={
                            "company_id": str(company_id),
                            "signal_type": "funding",
                            "source_url": "https://news.example.com/acme-series-b",
                            "source_type": "news",
                            "confidence": 0.9,
                            "summary": "Acme Rockets raised a $20M Series B.",
                            "business_implication": (
                                "Likely to expand engineering and tooling budget soon."
                            ),
                        },
                        name="record_signal",
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
        recorded_signal_id = UUID(result["signal_id"])
        recorded_rank = result["rank"]
        output = SignalAgentOutput(
            signal_id=recorded_signal_id,
            signal_type="funding",
            summary="Acme Rockets raised a $20M Series B.",
            event_date=None,
            source="https://news.example.com/acme-series-b",
            confidence=0.9,
            business_implication="Likely to expand engineering and tooling budget soon.",
            rank=recorded_rank,
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

    output = await runtime.run(
        SIGNAL_AGENT_DEFINITION, input=SignalAgentInput(company_id=company_id)
    )

    assert isinstance(output, SignalAgentOutput)
    assert len(signals.rows) == 1
    (signal,) = signals.rows.values()
    assert signal.signal_type == "funding"
    assert output.signal_id == signal.id

    expected_rank = rank_signal(
        signal_type=signal.signal_type,
        confidence=signal.confidence,
        event_at=signal.event_at,
        observed_at=signal.observed_at,
        now=datetime.now(UTC),
    )
    assert output.rank == expected_rank
