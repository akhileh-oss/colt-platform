"""Milestone 12's acceptance criterion, proven literally: "A real/mock trigger can create a
signal and rank it correctly" (CLAUDE.md §68).

Everything here is real except the Anthropic call itself: real Postgres, real RLS, a real
`SqlAlchemySignalRepository`/`RecordSignal`, and the literal "mock trigger" the acceptance
criterion names — `FakeSignalTriggerSource` (no real signal-source provider is named anywhere
in CLAUDE.md, unlike `SearchProvider`/`EnrichmentProvider`, so Milestone 12 builds no real
adapter; see this milestone's PR for the explicit scope note). The rank is independently
recomputed from the row queried back from Postgres and compared against the agent's own
output - not asserted from in-memory state.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr
from sqlalchemy import text

from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.signal_agent import SIGNAL_AGENT_DEFINITION, SignalAgentInput, SignalAgentOutput
from colt_agents.tools import build_poll_signal_sources_tool, build_record_signal_tool
from colt_ai import AnthropicGateway
from colt_application.signals import rank_signal
from colt_application.use_cases.record_signal import RecordSignal
from colt_config import AnthropicSettings
from colt_db.repositories.agent_run_repository import SqlAlchemyAgentRunRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.signal_repository import SqlAlchemySignalRepository
from colt_db.repositories.tool_call_repository import SqlAlchemyToolCallRepository
from colt_integrations.signals.fake import FakeSignalTriggerSource
from colt_integrations.signals.port import SignalTriggerPayload


def _usage() -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
    )


@pytest.mark.asyncio
async def test_a_mock_trigger_creates_a_signal_and_ranks_it_correctly(
    open_app_session: Any, two_organizations: tuple[Any, Any]
) -> None:
    org_a, _ = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        company_repo = await SqlAlchemyCompanyRepository.create(seed, org_a)
        company = await company_repo.add(name="Acme Rockets")

    trigger_source = FakeSignalTriggerSource(
        [
            SignalTriggerPayload(
                company_id=company.id,
                source="mock-newswire",
                observed_at=datetime.now(UTC),
                source_url="https://news.example.com/acme-series-b",
                source_type="news",
                raw_payload={"headline": "Acme Rockets raises $20M Series B"},
            )
        ]
    )

    calls: list[dict[str, Any]] = []

    async def fake_create(**kwargs: Any) -> Message:
        calls.append(kwargs)
        if len(calls) == 1:
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
        if len(calls) == 2:
            return Message(
                id="msg_2",
                content=[
                    ToolUseBlock(
                        id="toolu_2",
                        input={
                            "company_id": str(company.id),
                            "signal_type": "funding",
                            "source_url": "https://news.example.com/acme-series-b",
                            "source_type": "news",
                            "confidence": 0.9,
                            "summary": "Acme Rockets raised a $20M Series B.",
                            "business_implication": "Likely to expand engineering soon.",
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
        output = SignalAgentOutput(
            signal_id=UUID(result["signal_id"]),
            signal_type="funding",
            summary="Acme Rockets raised a $20M Series B.",
            event_date=None,
            source="https://news.example.com/acme-series-b",
            confidence=0.9,
            business_implication="Likely to expand engineering soon.",
            rank=result["rank"],
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

    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    client.messages.create = fake_create  # type: ignore[assignment]
    gateway = AnthropicGateway(
        AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )

    session = await open_app_session()
    async with session, session.begin():
        signals = await SqlAlchemySignalRepository.create(session, org_a)
        registry = ToolRegistry()
        registry.register(build_poll_signal_sources_tool(trigger_source))
        registry.register(build_record_signal_tool(RecordSignal(signals)))
        agent_runs = SqlAlchemyAgentRunRepository(session, org_a)
        tool_calls = SqlAlchemyToolCallRepository(session, org_a)
        runtime = AgentRuntime(gateway, registry, agent_runs, tool_calls)

        output = await runtime.run(
            SIGNAL_AGENT_DEFINITION, input=SignalAgentInput(company_id=company.id)
        )

        signal_rows = (
            (
                await session.execute(
                    text("SELECT * FROM signals WHERE organization_id = :org"), {"org": org_a}
                )
            )
            .mappings()
            .all()
        )

    assert isinstance(output, SignalAgentOutput)
    assert len(signal_rows) == 1
    signal_row = signal_rows[0]
    assert signal_row["id"] == output.signal_id
    assert signal_row["signal_type"] == "funding"
    assert signal_row["business_implication"] == "Likely to expand engineering soon."

    expected_rank = rank_signal(
        signal_type=signal_row["signal_type"],
        confidence=signal_row["confidence"],
        event_at=signal_row["event_at"],
        observed_at=signal_row["observed_at"],
        now=datetime.now(UTC),
    )
    assert output.rank == pytest.approx(expected_rank)
