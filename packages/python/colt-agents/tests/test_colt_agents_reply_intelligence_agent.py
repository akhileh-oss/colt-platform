"""`ReplyIntelligenceAgent` (CLAUDE.md §12.10, §23.1) — the full classification loop through
`AgentRuntime`, hermetically: in-memory `ConversationRepository`/`ConversationEventRepository`,
and a real `AsyncAnthropic` instance with only `.messages.create` replaced (the same pattern
every prior milestone's own tests establish). `tests/integration/test_reply_intelligence.py`
separately proves the same mechanism against real Postgres, proving Milestone 19's acceptance
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
from colt_agents.reply_intelligence_agent import (
    REPLY_INTELLIGENCE_AGENT_DEFINITION,
    ReplyClassification,
    ReplyIntelligenceAgentInput,
    ReplyIntent,
    Sentiment,
)
from colt_agents.runtime import AgentRuntime
from colt_agents.tools import build_record_reply_classification_tool
from colt_ai import AnthropicGateway
from colt_application.reply_classification import Urgency
from colt_application.use_cases.record_reply_classification import RecordReplyClassification
from colt_config import AnthropicSettings
from colt_domain import AgentRun, Conversation, ConversationEvent, ConversationState, ToolCall

NOW = datetime.now(UTC)


class FakeConversationRepository:
    def __init__(self, conversation: Conversation) -> None:
        self.conversation = conversation

    async def add(self, **kwargs: Any) -> Conversation:
        raise NotImplementedError

    async def get(self, conversation_id: UUID) -> Conversation | None:
        return self.conversation if conversation_id == self.conversation.id else None

    async def get_by_lead_and_channel(self, lead_id: UUID, channel: str) -> Conversation | None:
        raise NotImplementedError

    async def touch_last_activity(self, conversation_id: UUID, *, at: datetime) -> Conversation:
        raise NotImplementedError

    async def update_state(
        self, conversation_id: UUID, state: ConversationState, *, at: datetime
    ) -> Conversation:
        self.conversation = self.conversation.with_state(state, at=at)
        return self.conversation


class FakeConversationEventRepository:
    def __init__(self) -> None:
        self.added: list[ConversationEvent] = []

    async def add(self, **kwargs: Any) -> ConversationEvent:
        event = ConversationEvent(id=uuid4(), organization_id=uuid4(), created_at=NOW, **kwargs)
        self.added.append(event)
        return event

    async def list_by_conversation(self, conversation_id: UUID) -> list[ConversationEvent]:
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


async def test_a_high_urgency_classification_is_recorded_and_hands_off() -> None:
    conversation = Conversation(
        id=uuid4(),
        organization_id=uuid4(),
        lead_id=uuid4(),
        channel="email",
        created_at=NOW,
        updated_at=NOW,
    )
    conversations = FakeConversationRepository(conversation)
    conversation_events = FakeConversationEventRepository()
    registry = ToolRegistry()
    registry.register(
        build_record_reply_classification_tool(
            RecordReplyClassification(conversations, conversation_events)
        )
    )

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
                            "conversation_id": str(conversation.id),
                            "intent": "MEETING_REQUEST",
                            "sentiment": "POSITIVE",
                            "urgency": "HIGH",
                            "objection": None,
                            "asks_question": True,
                            "meeting_signal": True,
                            "recommended_state_transition": "QUESTION",
                            "confidence": 0.92,
                            "suggested_response": "Happy to set up a call this week.",
                        },
                        name="record_reply_classification",
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
        json.loads(last_tool_result["content"])
        output = ReplyClassification(
            conversation_id=conversation.id,
            intent=ReplyIntent.MEETING_REQUEST,
            sentiment=Sentiment.POSITIVE,
            urgency=Urgency.HIGH,
            objection=None,
            asks_question=True,
            meeting_signal=True,
            recommended_state_transition=ConversationState.QUESTION,
            confidence=0.92,
            suggested_response="Happy to set up a call this week.",
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
        REPLY_INTELLIGENCE_AGENT_DEFINITION,
        input=ReplyIntelligenceAgentInput(
            conversation_id=conversation.id,
            company_name="Acme Rockets",
            person_name="Jane Doe",
            subject="Re: hello",
            body="Yes, I'd love to grab 15 minutes this week - can we talk tomorrow?",
        ),
    )

    assert isinstance(output, ReplyClassification)
    assert output.recommended_state_transition == ConversationState.QUESTION
    # The model recommended QUESTION, but HIGH urgency always wins — the deterministic rule
    # this milestone's acceptance criterion depends on, not the model's own say.
    assert conversations.conversation.state == ConversationState.HUMAN_HANDOFF
    event_types = [e.event_type for e in conversation_events.added]
    assert event_types == ["reply_classified", "handoff_created"]
