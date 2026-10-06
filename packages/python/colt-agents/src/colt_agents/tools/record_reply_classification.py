"""`record_reply_classification` (CLAUDE.md §10.13, §11.2, §12.10, Milestone 19) — the one write
tool `ReplyIntelligenceAgent` may call. Applies the deterministic transition
(`colt_application.reply_classification.determine_conversation_transition`) and records the
`reply_classified` (and, if applicable, `handoff_created`) `ConversationEvent` rows via
`RecordReplyClassification` — never trusts the model's own `recommended_state_transition` as the
state actually applied.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.reply_classification import Urgency
from colt_application.use_cases.record_reply_classification import RecordReplyClassification
from colt_domain import ConversationState

TOOL_NAME = "record_reply_classification"
TOOL_VERSION = "v1"


class RecordReplyClassificationInput(BaseModel):
    conversation_id: UUID
    intent: str
    sentiment: str
    urgency: Urgency
    objection: str | None = None
    asks_question: bool
    meeting_signal: bool
    recommended_state_transition: ConversationState
    confidence: float
    suggested_response: str | None = None


class RecordReplyClassificationOutput(BaseModel):
    conversation_event_id: UUID
    applied_state_transition: str


def build_record_reply_classification_tool(
    record_reply_classification: RecordReplyClassification,
) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, RecordReplyClassificationInput)  # noqa: S101 -
        # guards an internal contract this tool's own `input_model` guarantees.
        event = await record_reply_classification(
            validated_input.conversation_id,
            intent=validated_input.intent,
            sentiment=validated_input.sentiment,
            urgency=validated_input.urgency,
            objection=validated_input.objection,
            asks_question=validated_input.asks_question,
            meeting_signal=validated_input.meeting_signal,
            recommended_state_transition=validated_input.recommended_state_transition,
            confidence=validated_input.confidence,
            suggested_response=validated_input.suggested_response,
            now=datetime.now(UTC),
        )
        return RecordReplyClassificationOutput(
            conversation_event_id=event.id,
            applied_state_transition=str(event.metadata["applied_state_transition"]),
        )

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Record this reply's classification against the real Conversation. The conversation "
            "state actually applied is computed deterministically from urgency and the "
            "conversation's current state - it may differ from recommended_state_transition "
            "(e.g. a HIGH urgency reply always produces a human handoff, and a terminal "
            "conversation never moves again)."
        ),
        input_model=RecordReplyClassificationInput,
        handler=handler,
    )
