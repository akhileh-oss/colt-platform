"""`MessagingAgent` (CLAUDE.md §12.9) — the full draft_message loop through `AgentRuntime`,
hermetically: in-memory `MessageRepository`/`EvidenceRepository`, and a real `AsyncAnthropic`
instance with only `.messages.create` replaced. `tests/integration/
test_personalization_and_messaging.py` separately proves the same mechanism against real
Postgres, proving Milestone 15's acceptance criterion literally.
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

from colt_agents.messaging_agent import (
    MESSAGING_AGENT_DEFINITION,
    MessagingAgentInput,
    MessagingAgentOutput,
)
from colt_agents.registry import ToolRegistry
from colt_agents.runtime import AgentRuntime
from colt_agents.tools import build_draft_message_tool
from colt_ai import AnthropicGateway
from colt_application.use_cases.draft_message import DraftMessage
from colt_config import AnthropicSettings
from colt_domain import AgentRun, Evidence, Message, ToolCall

NOW = datetime.now(UTC)


class FakeEvidenceRepository:
    def __init__(self, evidence: list[Evidence]) -> None:
        self._evidence = evidence

    async def add(self, **kwargs: object) -> Evidence:
        raise NotImplementedError

    async def get(self, evidence_id: UUID) -> Evidence | None:
        return next((e for e in self._evidence if e.id == evidence_id), None)

    async def list_by_entity(self, entity_type: str, entity_id: UUID) -> list[Evidence]:
        raise NotImplementedError


class FakeMessageRepository:
    def __init__(self) -> None:
        self.added: list[Message] = []

    async def add(self, **kwargs: Any) -> Message:
        message = Message(
            id=uuid4(),
            organization_id=uuid4(),
            created_at=NOW,
            updated_at=NOW,
            **{k: v for k, v in kwargs.items() if v is not None},
        )
        self.added.append(message)
        return message

    async def get(self, message_id: UUID) -> Message | None:
        raise NotImplementedError

    async def get_by_idempotency_key(self, idempotency_key: str) -> Message | None:
        raise NotImplementedError

    async def get_by_provider_message_id(self, provider_message_id: str) -> Message | None:
        raise NotImplementedError

    async def list_by_campaign(self, campaign_id: UUID) -> list[Message]:
        raise NotImplementedError

    async def list_by_lead_and_step(
        self, lead_id: UUID, sequence_step_id: UUID | None
    ) -> list[Message]:
        raise NotImplementedError

    async def update_approval_status(self, message_id: UUID, *, approval_status: str) -> Message:
        raise NotImplementedError

    async def update_send_result(
        self,
        message_id: UUID,
        *,
        status: str,
        sent_at: datetime,
        provider_message_id: str | None,
        idempotency_key: str | None = None,
    ) -> Message:
        raise NotImplementedError

    async def count_sent_since(self, campaign_id: UUID, since: datetime) -> int:
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


@pytest.mark.asyncio
async def test_messaging_agent_drafts_a_message_retaining_evidence_ids() -> None:
    evidence = Evidence(
        id=uuid4(),
        organization_id=uuid4(),
        entity_type="Company",
        entity_id=uuid4(),
        claim="They raised a $20M Series B.",
        source_url="https://example.com/news",
        observed_at=NOW,
        created_at=NOW,
    )
    lead_id, campaign_id = uuid4(), uuid4()

    messages = FakeMessageRepository()
    registry = ToolRegistry()
    registry.register(
        build_draft_message_tool(DraftMessage(messages, FakeEvidenceRepository([evidence])))
    )

    drafted_body = "Congrats on the $20M Series B - curious how you're scaling the team."
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
                        input={
                            "campaign_id": str(campaign_id),
                            "lead_id": str(lead_id),
                            "channel": "email",
                            "body": drafted_body,
                            "evidence_ids": [str(evidence.id)],
                        },
                        name="draft_message",
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
        output = MessagingAgentOutput(
            message_id=UUID(result["message_id"]),
            channel=result["channel"],
            subject=result["subject"],
            body=result["body"],
            evidence_ids=[UUID(v) for v in result["evidence_ids"]],
        )
        return AnthropicMessage(
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
        MESSAGING_AGENT_DEFINITION,
        input=MessagingAgentInput(
            lead_id=lead_id,
            campaign_id=campaign_id,
            channel="email",
            angle="Open with the Series B.",
            business_relevance="Fresh funding usually means headcount growth.",
            evidence_ids=[evidence.id],
        ),
    )

    assert isinstance(output, MessagingAgentOutput)
    assert output.evidence_ids == [evidence.id]
    assert output.body == drafted_body
    (message,) = messages.added
    assert message.evidence_ids == [evidence.id]


@pytest.mark.asyncio
async def test_messaging_agent_tool_rejects_unsupported_evidence() -> None:
    messages = FakeMessageRepository()
    registry = ToolRegistry()
    registry.register(build_draft_message_tool(DraftMessage(messages, FakeEvidenceRepository([]))))
    lead_id, campaign_id, bogus_evidence_id = uuid4(), uuid4(), uuid4()

    async def fake_create(**kwargs: Any) -> AnthropicMessage:
        if kwargs["messages"][-1]["role"] == "user" and len(kwargs["messages"]) == 1:
            return AnthropicMessage(
                id="msg_1",
                content=[
                    ToolUseBlock(
                        id="toolu_1",
                        input={
                            "campaign_id": str(campaign_id),
                            "lead_id": str(lead_id),
                            "channel": "email",
                            "body": "Hi there.",
                            "evidence_ids": [str(bogus_evidence_id)],
                        },
                        name="draft_message",
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
        assert last_tool_result.get("is_error") is True
        output = MessagingAgentOutput(
            message_id=uuid4(),
            channel="email",
            subject=None,
            body="Error: unsupported evidence",
            evidence_ids=[],
        )
        return AnthropicMessage(
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

    await runtime.run(
        MESSAGING_AGENT_DEFINITION,
        input=MessagingAgentInput(
            lead_id=lead_id,
            campaign_id=campaign_id,
            channel="email",
            angle="n/a",
            business_relevance="n/a",
            evidence_ids=[bogus_evidence_id],
        ),
    )

    assert messages.added == []
