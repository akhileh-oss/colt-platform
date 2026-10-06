"""`ProcessInboundEmail` (CLAUDE.md §29, §29.1, Milestone 17).

"Incoming messages must resolve to the correct Colt conversation" (§29.1). This use case is
that resolution mechanism: it takes the inbound email's `In-Reply-To` header, finds the
`Message` we originally sent with that `provider_message_id`, and threads the reply onto that
lead's email `Conversation` — creating one if this is the lead's first reply.

Deliberately out of scope: classifying *what* the reply means (positive, objection, a
question, ...) is `ReplyIntelligenceAgent`'s job (§12.10, Milestone 19). This use case only
records that a reply arrived and threads it; it does not interpret it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from colt_application.errors import NotFoundError
from colt_application.ports.conversation_event_repository import ConversationEventRepository
from colt_application.ports.conversation_repository import ConversationRepository
from colt_application.ports.message_repository import MessageRepository
from colt_domain import ConversationEvent

_EMAIL_CHANNEL = "email"


class ProcessInboundEmail:
    def __init__(
        self,
        messages: MessageRepository,
        conversations: ConversationRepository,
        conversation_events: ConversationEventRepository,
    ) -> None:
        self._messages = messages
        self._conversations = conversations
        self._conversation_events = conversation_events

    async def __call__(
        self,
        *,
        provider_message_id: str,
        in_reply_to: str,
        from_email: str,
        subject: str | None,
        body: str,
        received_at: datetime,
    ) -> ConversationEvent:
        original = await self._messages.get_by_provider_message_id(in_reply_to)
        if original is None:
            raise NotFoundError(
                f"No outbound message with provider_message_id {in_reply_to!r} — cannot thread "
                "this reply to a conversation."
            )

        conversation = await self._conversations.get_by_lead_and_channel(
            original.lead_id, _EMAIL_CHANNEL
        )
        if conversation is None:
            conversation = await self._conversations.add(
                lead_id=original.lead_id, channel=_EMAIL_CHANNEL, last_activity_at=received_at
            )
        await self._conversations.touch_last_activity(conversation.id, at=received_at)

        metadata: dict[str, Any] = {
            "provider_message_id": provider_message_id,
            "in_reply_to": in_reply_to,
            "from_email": from_email,
            "subject": subject,
            "body": body,
        }
        return await self._conversation_events.add(
            conversation_id=conversation.id,
            event_type="message_received",
            occurred_at=received_at,
            metadata=metadata,
        )
