"""`RecordReplyClassification` (CLAUDE.md §10.13, §11.2, §12.10, Milestone 19)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.reply_classification import Urgency
from colt_application.use_cases.record_reply_classification import RecordReplyClassification
from colt_domain import Conversation, ConversationEvent, ConversationState

NOW = datetime.now(UTC)


class FakeConversationRepository:
    def __init__(self, conversation: Conversation | None) -> None:
        self.conversation = conversation
        self.state_updates: list[ConversationState] = []

    async def add(self, **kwargs: Any) -> Conversation:
        raise NotImplementedError

    async def get(self, conversation_id: UUID) -> Conversation | None:
        return (
            self.conversation
            if self.conversation and conversation_id == self.conversation.id
            else None
        )

    async def get_by_lead_and_channel(self, lead_id: UUID, channel: str) -> Conversation | None:
        raise NotImplementedError

    async def touch_last_activity(self, conversation_id: UUID, *, at: datetime) -> Conversation:
        raise NotImplementedError

    async def update_state(
        self, conversation_id: UUID, state: ConversationState, *, at: datetime
    ) -> Conversation:
        assert self.conversation is not None
        self.state_updates.append(state)
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


def _conversation(state: ConversationState = ConversationState.OPEN) -> Conversation:
    return Conversation(
        id=uuid4(),
        organization_id=uuid4(),
        lead_id=uuid4(),
        channel="email",
        state=state,
        created_at=NOW,
        updated_at=NOW,
    )


def _call_kwargs(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "intent": "INTERESTED",
        "sentiment": "POSITIVE",
        "urgency": Urgency.LOW,
        "objection": None,
        "asks_question": False,
        "meeting_signal": False,
        "recommended_state_transition": ConversationState.POSITIVE,
        "confidence": 0.9,
        "suggested_response": "Happy to set up a call this week.",
        "now": NOW,
    }
    defaults.update(overrides)
    return defaults


@pytest.mark.asyncio
async def test_a_low_urgency_classification_applies_the_recommended_state() -> None:
    conversation = _conversation()
    conversations = FakeConversationRepository(conversation)
    conversation_events = FakeConversationEventRepository()
    record = RecordReplyClassification(conversations, conversation_events)

    event = await record(conversation.id, **_call_kwargs())

    assert event.event_type == "reply_classified"
    assert conversations.state_updates == [ConversationState.POSITIVE]
    assert event.metadata["applied_state_transition"] == "POSITIVE"
    assert len(conversation_events.added) == 1


@pytest.mark.asyncio
async def test_a_high_urgency_classification_hands_off_and_records_a_second_event() -> None:
    conversation = _conversation()
    conversations = FakeConversationRepository(conversation)
    conversation_events = FakeConversationEventRepository()
    record = RecordReplyClassification(conversations, conversation_events)

    await record(
        conversation.id,
        **_call_kwargs(
            urgency=Urgency.HIGH, recommended_state_transition=ConversationState.QUESTION
        ),
    )

    assert conversations.state_updates == [ConversationState.HUMAN_HANDOFF]
    event_types = [e.event_type for e in conversation_events.added]
    assert event_types == ["reply_classified", "handoff_created"]
    assert conversation_events.added[1].metadata["reason"] == "high_urgency"


@pytest.mark.asyncio
async def test_a_terminal_conversation_is_not_moved_and_gets_no_state_update_call() -> None:
    conversation = _conversation(state=ConversationState.UNSUBSCRIBED)
    conversations = FakeConversationRepository(conversation)
    conversation_events = FakeConversationEventRepository()
    record = RecordReplyClassification(conversations, conversation_events)

    event = await record(conversation.id, **_call_kwargs(urgency=Urgency.HIGH))

    assert conversations.state_updates == []
    assert event.metadata["applied_state_transition"] == "UNSUBSCRIBED"


@pytest.mark.asyncio
async def test_raises_not_found_for_an_unknown_conversation() -> None:
    conversations = FakeConversationRepository(None)
    conversation_events = FakeConversationEventRepository()
    record = RecordReplyClassification(conversations, conversation_events)

    with pytest.raises(NotFoundError):
        await record(uuid4(), **_call_kwargs())
