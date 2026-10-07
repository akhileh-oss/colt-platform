"""`ReplyIntelligenceAgent`'s golden evaluation suite (CLAUDE.md §45.5, §68, Milestone 23).

Covers this milestone's **classification accuracy** Build item (§45.5's own Evaluate list).
Each golden case drives a canned classification through the real
`record_reply_classification` tool -> `RecordReplyClassification` -> `determine_conversation_
transition` path and checks the conversation's *actual, persisted* state — not the model's raw
`recommended_state_transition` — against the case's expected label. That distinction is the
point: the last case recommends `QUESTION` but is `HIGH` urgency, which the deterministic
transition rule always overrides to `HUMAN_HANDOFF` regardless of what the model recommended
(§12.10, the same "model judges, code decides" split this codebase already establishes
elsewhere) — a classification-accuracy suite that only checked the model's own recommendation
would miss that override entirely.

Hermetic throughout: the same fake `Conversation`/`ConversationEvent` repositories and faked
`.messages.create` pattern `test_colt_agents_reply_intelligence_agent.py` already establishes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr

from colt_agents.evals.report import EvalCaseOutcome, EvalReport, build_cost_report
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

pytestmark = pytest.mark.evals


class _FakeConversationRepository:
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


class _FakeConversationEventRepository:
    def __init__(self) -> None:
        self.added: list[ConversationEvent] = []

    async def add(self, **kwargs: Any) -> ConversationEvent:
        event = ConversationEvent(
            id=uuid4(), organization_id=uuid4(), created_at=datetime.now(UTC), **kwargs
        )
        self.added.append(event)
        return event

    async def list_by_conversation(self, conversation_id: UUID) -> list[ConversationEvent]:
        raise NotImplementedError


class _FakeAgentRunRepository:
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


class _FakeToolCallRepository:
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


async def _run_classification_case(
    *,
    body: str,
    intent: ReplyIntent,
    sentiment: Sentiment,
    urgency: Urgency,
    recommended_state_transition: ConversationState,
    confidence: float = 0.85,
) -> tuple[ReplyClassification, ConversationState, AgentRun]:
    conversation = Conversation(
        id=uuid4(),
        organization_id=uuid4(),
        lead_id=uuid4(),
        channel="email",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    conversations = _FakeConversationRepository(conversation)
    conversation_events = _FakeConversationEventRepository()
    registry = ToolRegistry()
    registry.register(
        build_record_reply_classification_tool(
            RecordReplyClassification(conversations, conversation_events)
        )
    )

    classification = ReplyClassification(
        conversation_id=conversation.id,
        intent=intent,
        sentiment=sentiment,
        urgency=urgency,
        objection=None,
        asks_question=False,
        meeting_signal=intent == ReplyIntent.MEETING_REQUEST,
        recommended_state_transition=recommended_state_transition,
        confidence=confidence,
        suggested_response="A suggested response a human reviews before sending.",
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
                            "intent": intent.value,
                            "sentiment": sentiment.value,
                            "urgency": urgency.value,
                            "objection": None,
                            "asks_question": False,
                            "meeting_signal": classification.meeting_signal,
                            "recommended_state_transition": recommended_state_transition.value,
                            "confidence": confidence,
                            "suggested_response": classification.suggested_response,
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
        return Message(
            id="msg_2",
            content=[TextBlock(text=classification.model_dump_json(), type="text")],
            model=kwargs["model"],
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage=_usage(),
        )

    agent_runs = _FakeAgentRunRepository()
    tool_calls = _FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    output = await runtime.run(
        REPLY_INTELLIGENCE_AGENT_DEFINITION,
        input=ReplyIntelligenceAgentInput(
            conversation_id=conversation.id,
            company_name="Acme Rockets",
            person_name="Jane Doe",
            subject="Re: hello",
            body=body,
        ),
    )
    assert isinstance(output, ReplyClassification)
    (run,) = agent_runs.runs.values()
    return output, conversations.conversation.state, run


async def test_reply_intelligence_agent_golden_suite_classification_accuracy() -> None:
    outcomes: list[EvalCaseOutcome] = []
    agent_runs: list[AgentRun] = []

    _, positive_state, positive_run = await _run_classification_case(
        body="Yes, this looks great, let's talk.",
        intent=ReplyIntent.INTERESTED,
        sentiment=Sentiment.POSITIVE,
        urgency=Urgency.MEDIUM,
        recommended_state_transition=ConversationState.POSITIVE,
    )
    outcomes.append(
        EvalCaseOutcome(
            case_id="positive_reply_recommends_positive",
            passed=positive_state == ConversationState.POSITIVE,
            detail=f"actual state={positive_state}",
        )
    )
    agent_runs.append(positive_run)

    _, objection_state, objection_run = await _run_classification_case(
        body="This is too expensive for us right now.",
        intent=ReplyIntent.OBJECTION,
        sentiment=Sentiment.NEGATIVE,
        urgency=Urgency.MEDIUM,
        recommended_state_transition=ConversationState.OBJECTION,
    )
    outcomes.append(
        EvalCaseOutcome(
            case_id="objection_reply_recommends_objection",
            passed=objection_state == ConversationState.OBJECTION,
            detail=f"actual state={objection_state}",
        )
    )
    agent_runs.append(objection_run)

    high_urgency_output, high_urgency_state, high_urgency_run = await _run_classification_case(
        body="Can we talk tomorrow? This is urgent.",
        intent=ReplyIntent.MEETING_REQUEST,
        sentiment=Sentiment.POSITIVE,
        urgency=Urgency.HIGH,
        recommended_state_transition=ConversationState.QUESTION,
    )
    # The model recommended QUESTION; HIGH urgency always forces HUMAN_HANDOFF regardless
    # (CLAUDE.md §12.10's deterministic override) - the behavior this case actually checks.
    outcomes.append(
        EvalCaseOutcome(
            case_id="high_urgency_always_forces_handoff",
            passed=(
                high_urgency_output.recommended_state_transition == ConversationState.QUESTION
                and high_urgency_state == ConversationState.HUMAN_HANDOFF
            ),
            detail=f"model recommended={high_urgency_output.recommended_state_transition}, "
            f"actual state={high_urgency_state}",
        )
    )
    agent_runs.append(high_urgency_run)

    report = EvalReport(agent_name=REPLY_INTELLIGENCE_AGENT_DEFINITION.name, outcomes=outcomes)
    assert report.pass_rate == 1.0, report.failures

    (cost_row,) = build_cost_report(agent_runs)
    assert cost_row.run_count == 3
