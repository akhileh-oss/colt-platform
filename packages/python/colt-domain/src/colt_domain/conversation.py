"""The Conversation entity (CLAUDE.md §10.12) — a channel thread with a lead.

`ConversationState` is the closed state machine from §11.2. `OPEN` is the only non-terminal
value; the rest are outcomes a reply is classified into by `ReplyIntelligenceAgent` (Milestone
19) — modeled as flat siblings of one field rather than a tree, since a conversation is always in
exactly one of them.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ConversationState(StrEnum):
    OPEN = "OPEN"
    POSITIVE = "POSITIVE"
    QUESTION = "QUESTION"
    OBJECTION = "OBJECTION"
    NOT_NOW = "NOT_NOW"
    NOT_INTERESTED = "NOT_INTERESTED"
    UNSUBSCRIBED = "UNSUBSCRIBED"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"


class Conversation(BaseModel):
    """A channel thread (email, LinkedIn, ...) with one lead."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    lead_id: UUID
    channel: str
    state: ConversationState = ConversationState.OPEN
    last_activity_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("channel")
    @classmethod
    def _channel_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Conversation channel must not be blank.")
        return value

    def with_state(self, state: ConversationState, *, at: datetime) -> Self:
        return self.model_copy(update={"state": state, "updated_at": at})
