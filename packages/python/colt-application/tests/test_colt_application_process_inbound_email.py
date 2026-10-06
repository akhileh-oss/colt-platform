"""`ProcessInboundEmail` (CLAUDE.md §29.1, Milestone 17)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.use_cases.process_inbound_email import ProcessInboundEmail
from colt_domain import Conversation, ConversationEvent, ConversationState, Message

NOW = datetime.now(UTC)


class FakeMessageRepository:
    def __init__(self, message: Message | None) -> None:
        self._message = message

    async def add(self, **kwargs: Any) -> Message:
        raise NotImplementedError

    async def get(self, message_id: UUID) -> Message | None:
        raise NotImplementedError

    async def get_by_idempotency_key(self, idempotency_key: str) -> Message | None:
        raise NotImplementedError

    async def get_by_provider_message_id(self, provider_message_id: str) -> Message | None:
        if self._message and self._message.provider_message_id == provider_message_id:
            return self._message
        return None

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


class FakeConversationRepository:
    def __init__(self, existing: Conversation | None = None) -> None:
        self.existing = existing
        self.added: list[Conversation] = []
        self.touched: list[UUID] = []

    async def add(self, **kwargs: Any) -> Conversation:
        conversation = Conversation(
            id=uuid4(), organization_id=uuid4(), created_at=NOW, updated_at=NOW, **kwargs
        )
        self.added.append(conversation)
        return conversation

    async def get(self, conversation_id: UUID) -> Conversation | None:
        raise NotImplementedError

    async def get_by_lead_and_channel(self, lead_id: UUID, channel: str) -> Conversation | None:
        return self.existing

    async def touch_last_activity(self, conversation_id: UUID, *, at: datetime) -> Conversation:
        self.touched.append(conversation_id)
        target = self.existing or self.added[-1]
        return target.model_copy(update={"last_activity_at": at})

    async def update_state(
        self, conversation_id: UUID, state: ConversationState, *, at: datetime
    ) -> Conversation:
        raise NotImplementedError


class FakeConversationEventRepository:
    def __init__(self) -> None:
        self.added: list[ConversationEvent] = []

    async def add(self, **kwargs: Any) -> ConversationEvent:
        event = ConversationEvent(id=uuid4(), organization_id=uuid4(), created_at=NOW, **kwargs)
        self.added.append(event)
        return event

    async def list_by_conversation(self, conversation_id: UUID) -> list[ConversationEvent]:
        raise NotImplementedError


def _sent_message(provider_message_id: str) -> Message:
    return Message(
        id=uuid4(),
        organization_id=uuid4(),
        campaign_id=uuid4(),
        lead_id=uuid4(),
        channel="email",
        body="Hello.",
        status="SENT",
        provider_message_id=provider_message_id,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_threads_a_reply_onto_a_new_conversation_when_none_exists() -> None:
    original = _sent_message("<outbound-1@colt.local>")
    messages = FakeMessageRepository(original)
    conversations = FakeConversationRepository(existing=None)
    conversation_events = FakeConversationEventRepository()
    process = ProcessInboundEmail(messages, conversations, conversation_events)

    event = await process(
        provider_message_id="<inbound-1@example.com>",
        in_reply_to="<outbound-1@colt.local>",
        from_email="lead@example.com",
        subject="Re: hello",
        body="Sounds good.",
        received_at=NOW,
    )

    assert event.event_type == "message_received"
    (created,) = conversations.added
    assert created.lead_id == original.lead_id
    assert created.channel == "email"
    assert conversations.touched == [created.id]
    assert event.metadata["from_email"] == "lead@example.com"


@pytest.mark.asyncio
async def test_threads_a_reply_onto_an_existing_conversation() -> None:
    original = _sent_message("<outbound-2@colt.local>")
    existing = Conversation(
        id=uuid4(),
        organization_id=original.organization_id,
        lead_id=original.lead_id,
        channel="email",
        created_at=NOW,
        updated_at=NOW,
    )
    messages = FakeMessageRepository(original)
    conversations = FakeConversationRepository(existing=existing)
    conversation_events = FakeConversationEventRepository()
    process = ProcessInboundEmail(messages, conversations, conversation_events)

    event = await process(
        provider_message_id="<inbound-2@example.com>",
        in_reply_to="<outbound-2@colt.local>",
        from_email="lead@example.com",
        subject=None,
        body="Thanks.",
        received_at=NOW,
    )

    assert conversations.added == []
    assert conversations.touched == [existing.id]
    (recorded,) = conversation_events.added
    assert recorded.conversation_id == existing.id
    assert event is recorded


@pytest.mark.asyncio
async def test_raises_not_found_when_the_reply_does_not_resolve_to_an_outbound_message() -> None:
    messages = FakeMessageRepository(None)
    conversations = FakeConversationRepository()
    conversation_events = FakeConversationEventRepository()
    process = ProcessInboundEmail(messages, conversations, conversation_events)

    with pytest.raises(NotFoundError):
        await process(
            provider_message_id="<inbound-3@example.com>",
            in_reply_to="<unknown@colt.local>",
            from_email="lead@example.com",
            subject=None,
            body="Hi.",
            received_at=NOW,
        )
