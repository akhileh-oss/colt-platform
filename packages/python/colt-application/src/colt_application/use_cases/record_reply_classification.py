"""`RecordReplyClassification` (CLAUDE.md §10.13, §11.2, §12.10, §23.1, Milestone 19) — the one
write `ReplyIntelligenceAgent` may call, mirroring `DraftMessage`'s role for `MessagingAgent`.

Applies `colt_application.reply_classification.determine_conversation_transition` (never the
model's own `recommended_state_transition` directly), records a `reply_classified`
`ConversationEvent` carrying every §12.10 field plus the suggested response (read by a human,
never sent automatically — Milestone 19 names "suggested response generation" as a Build item,
not an outbound send), and — only when the applied transition actually is `HUMAN_HANDOFF` —
records a second, distinct `handoff_created` event, since §10.13 lists both as their own event
types, not one folded into the other.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.errors import NotFoundError
from colt_application.ports.conversation_event_repository import ConversationEventRepository
from colt_application.ports.conversation_repository import ConversationRepository
from colt_application.reply_classification import Urgency, determine_conversation_transition
from colt_domain import ConversationEvent, ConversationState


class RecordReplyClassification:
    def __init__(
        self,
        conversations: ConversationRepository,
        conversation_events: ConversationEventRepository,
    ) -> None:
        self._conversations = conversations
        self._conversation_events = conversation_events

    async def __call__(
        self,
        conversation_id: UUID,
        *,
        intent: str,
        sentiment: str,
        urgency: Urgency,
        objection: str | None,
        asks_question: bool,
        meeting_signal: bool,
        recommended_state_transition: ConversationState,
        confidence: float,
        suggested_response: str | None,
        now: datetime,
    ) -> ConversationEvent:
        conversation = await self._conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError(f"No conversation found with id {conversation_id}.")

        applied_state = determine_conversation_transition(
            current_state=conversation.state,
            recommended_state=recommended_state_transition,
            urgency=urgency,
        )
        if applied_state != conversation.state:
            await self._conversations.update_state(conversation_id, applied_state, at=now)

        classification_event = await self._conversation_events.add(
            conversation_id=conversation_id,
            event_type="reply_classified",
            occurred_at=now,
            metadata={
                "intent": intent,
                "sentiment": sentiment,
                "urgency": urgency.value,
                "objection": objection,
                "asks_question": asks_question,
                "meeting_signal": meeting_signal,
                "recommended_state_transition": recommended_state_transition.value,
                "applied_state_transition": applied_state.value,
                "confidence": confidence,
                "suggested_response": suggested_response,
            },
        )

        if applied_state == ConversationState.HUMAN_HANDOFF:
            await self._conversation_events.add(
                conversation_id=conversation_id,
                event_type="handoff_created",
                occurred_at=now,
                metadata={
                    "reason": "high_urgency" if urgency is Urgency.HIGH else "model_recommended"
                },
            )

        return classification_event
