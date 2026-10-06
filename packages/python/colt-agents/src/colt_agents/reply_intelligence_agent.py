"""The ReplyIntelligenceAgent (CLAUDE.md §12.10, §23.1): classifies one inbound reply.

The model forms the judgment §12.10's minimum output schema asks for — `intent`, `sentiment`,
`urgency`, `objection`, `asks_question`, `meeting_signal`, `recommended_state_transition`,
`confidence`, plus a `suggested_response` a human reads before ever sending anything (Milestone
19's own "suggested response generation" Build item, never an automated send). What actually
happens to the `Conversation`'s state is never this agent's own `recommended_state_transition`
taken verbatim — `record_reply_classification`'s own use case
(`colt_application.reply_classification.determine_conversation_transition`) decides that
deterministically, the same "model judges, code decides" split `ScoringAgent` (§12.7) already
established.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, field_validator

from colt_agents.definition import AgentDefinition
from colt_application.reply_classification import Urgency
from colt_config import ModelClass
from colt_domain import ConversationState

AGENT_NAME = "reply-intelligence-agent"
AGENT_VERSION = "v1"


#: §12.10 gives no closed vocabulary for `intent` — this milestone's own documented, minimal
#: design decision, the same reasoning `CampaignStatus` (Milestone 14) and `Urgency`
#: (`colt_application.reply_classification`) already apply where CLAUDE.md names a field
#: without enumerating its values.
class ReplyIntent(StrEnum):
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    QUESTION = "QUESTION"
    OBJECTION = "OBJECTION"
    MEETING_REQUEST = "MEETING_REQUEST"
    OUT_OF_OFFICE = "OUT_OF_OFFICE"
    OTHER = "OTHER"


class Sentiment(StrEnum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


#: §11.2's closed conversation-state machine, minus the two values a classification can never
#: recommend: `OPEN` (the starting state, never a destination) and `UNSUBSCRIBED` (an explicit
#: unsubscribe link/request is its own mechanism — `UnsubscribeByToken`, Milestone 17 — not a
#: reply classification's guess).
_RECOMMENDABLE_STATES = frozenset(
    {
        ConversationState.POSITIVE,
        ConversationState.QUESTION,
        ConversationState.OBJECTION,
        ConversationState.NOT_NOW,
        ConversationState.NOT_INTERESTED,
        ConversationState.HUMAN_HANDOFF,
    }
)


class ReplyClassification(BaseModel):
    conversation_id: UUID
    intent: ReplyIntent
    sentiment: Sentiment
    urgency: Urgency
    objection: str | None = None
    asks_question: bool
    meeting_signal: bool
    recommended_state_transition: ConversationState
    confidence: float
    suggested_response: str | None = None

    @field_validator("recommended_state_transition")
    @classmethod
    def _recommendable(cls, value: ConversationState) -> ConversationState:
        if value not in _RECOMMENDABLE_STATES:
            allowed = sorted(s.value for s in _RECOMMENDABLE_STATES)
            raise ValueError(
                f"{value.value} is not a state a reply classification may recommend "
                f"(CLAUDE.md §12.10) — must be one of {allowed}."
            )
        return value


class ReplyIntelligenceAgentInput(BaseModel):
    conversation_id: UUID
    company_name: str
    person_name: str
    subject: str | None
    body: str


REPLY_INTELLIGENCE_AGENT_DEFINITION = AgentDefinition(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    purpose=(
        "Classify one inbound reply - intent, sentiment, urgency, objection, whether it asks a "
        "question or signals wanting a meeting, the conversation state it recommends, and a "
        "suggested (never auto-sent) response (CLAUDE.md §12.10)."
    ),
    input_schema=ReplyIntelligenceAgentInput,
    output_schema=ReplyClassification,
    allowed_tools=frozenset({"record_reply_classification"}),
    model_policy=ModelClass.STANDARD,
    max_tool_calls=3,
    timeout_seconds=90.0,
)
