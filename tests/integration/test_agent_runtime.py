"""Milestone 09's acceptance criterion, proven literally: "A test agent can execute a typed
tool, return schema-valid output, and produce a complete audit trail" (CLAUDE.md §68).

Everything in this test is real except the Anthropic call itself: real Postgres, real RLS, a
real `Lead` seeded through `SqlAlchemyLeadRepository`, a real `GetLead` application use case,
a real `get_lead` typed tool, and real `AgentRun`/`ToolCall` rows written by `AgentRuntime` and
then independently queried back — the "complete audit trail" the acceptance criterion asks for.
The one substitution is a real `AsyncAnthropic` instance with only `.messages.create` replaced,
for the same reason Milestone 08's own tests make it: no real Anthropic API key exists in this
environment. See that milestone's PR, and this one's, for what that leaves unverified.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.example_agent import (
    EXAMPLE_AGENT_DEFINITION,
    ExampleAgentInput,
    ExampleAgentOutput,
)
from colt_agents.tools import build_get_lead_tool
from colt_ai import AnthropicGateway
from colt_application import GetLead
from colt_config import AnthropicSettings
from colt_db.repositories.agent_run_repository import SqlAlchemyAgentRunRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.tool_call_repository import SqlAlchemyToolCallRepository

SessionFactory = Callable[[], Awaitable[AsyncSession]]


def _usage(input_tokens: int, output_tokens: int) -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


@pytest.mark.asyncio
async def test_agent_executes_a_typed_tool_and_produces_a_complete_audit_trail(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        company_repo = await SqlAlchemyCompanyRepository.create(seed, org_a)
        company = await company_repo.add(name="Acme Rockets")
        person_id = (
            await seed.execute(
                text(
                    "INSERT INTO people (organization_id, company_id, full_name) "
                    "VALUES (:org_id, :company_id, 'Jane Doe') RETURNING id"
                ),
                {"org_id": org_a, "company_id": company.id},
            )
        ).scalar_one()
        lead_repo = SqlAlchemyLeadRepository(seed, org_a)
        lead = await lead_repo.add(company_id=company.id, person_id=person_id)

    tool_use_block = ToolUseBlock(
        id="toolu_1", input={"lead_id": str(lead.id)}, name="get_lead", type="tool_use"
    )
    final_output = ExampleAgentOutput(
        summary="Jane Doe at Acme Rockets, status NEW.", lead_status="NEW"
    )

    calls: list[dict[str, Any]] = []

    async def fake_create(**kwargs: Any) -> Message:
        calls.append(kwargs)
        if len(calls) == 1:
            return Message(
                id="msg_1",
                content=[tool_use_block],
                model=kwargs["model"],
                role="assistant",
                stop_reason="tool_use",
                stop_sequence=None,
                type="message",
                usage=_usage(50, 10),
            )
        return Message(
            id="msg_2",
            content=[TextBlock(text=final_output.model_dump_json(), type="text")],
            model=kwargs["model"],
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage=_usage(80, 20),
        )

    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    client.messages.create = fake_create  # type: ignore[assignment]
    gateway = AnthropicGateway(
        AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )

    session = await open_app_session()
    async with session, session.begin():
        lead_repo_a = await SqlAlchemyLeadRepository.create(session, org_a)
        registry = ToolRegistry()
        registry.register(build_get_lead_tool(GetLead(lead_repo_a)))
        agent_runs = SqlAlchemyAgentRunRepository(session, org_a)
        tool_calls = SqlAlchemyToolCallRepository(session, org_a)
        runtime = AgentRuntime(gateway, registry, agent_runs, tool_calls)

        output = await runtime.run(
            EXAMPLE_AGENT_DEFINITION, input=ExampleAgentInput(lead_id=lead.id)
        )

        run_rows = (
            (
                await session.execute(
                    text("SELECT * FROM agent_runs WHERE organization_id = :org"), {"org": org_a}
                )
            )
            .mappings()
            .all()
        )
        tool_call_rows = (
            (
                await session.execute(
                    text("SELECT * FROM tool_calls WHERE organization_id = :org"), {"org": org_a}
                )
            )
            .mappings()
            .all()
        )

    # The model got a real tool call for real: it saw the tool schema and the structured
    # output schema on the very first turn, before anything else happened.
    assert calls[0]["tools"][0]["name"] == "get_lead"
    assert calls[0]["output_config"]["format"]["schema"]["title"] == "ExampleAgentOutput"

    # Schema-valid output.
    assert isinstance(output, ExampleAgentOutput)
    assert output.lead_status == "NEW"

    # A complete, independently-queryable audit trail.
    assert len(run_rows) == 1
    run_row = run_rows[0]
    assert run_row["status"] == "COMPLETED"
    assert run_row["agent_name"] == "example-agent"
    assert run_row["model_name"] == gateway.model_for(EXAMPLE_AGENT_DEFINITION.model_policy)
    assert run_row["input_tokens"] == 130  # 50 + 80
    assert run_row["output_tokens"] == 30  # 10 + 20
    assert run_row["tool_tokens"] == 60  # the tool_use turn's 50 + 10
    assert run_row["estimated_cost_usd"] is not None
    assert run_row["output_json"]["lead_status"] == "NEW"

    assert len(tool_call_rows) == 1
    tool_call_row = tool_call_rows[0]
    assert tool_call_row["agent_run_id"] == run_row["id"]
    assert tool_call_row["tool_name"] == "get_lead"
    assert tool_call_row["status"] == "SUCCEEDED"
    assert str(lead.id) in tool_call_row["arguments_redacted"]
    assert tool_call_row["result_summary"] is not None
