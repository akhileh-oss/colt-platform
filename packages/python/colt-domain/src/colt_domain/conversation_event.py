"""The ConversationEvent entity (CLAUDE.md §10.13) — an append-only timeline entry on a
`Conversation`. Never built before Milestone 17: §10.5 lists it among the core domain model's
entities, but no prior milestone's Build list named it as a deliverable, and no use case before
this one's `ProcessInboundEmail`/`ProcessBounce` ever needed to write one.

`event_type` is a plain, open-vocabulary string, not a closed `StrEnum` — unlike `LeadStatus`/
`ConversationState` (§11's "do not let LLMs invent arbitrary statuses"), §10.13 itself lists its
examples as "events such as," explicitly open-ended (new event kinds are expected as new
channels/trackers land), so the same closed-enum treatment would misrepresent the spec.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ConversationEvent(BaseModel):
    """One append-only timeline entry — a message sent/received, an open/click, a reply
    classified, a handoff created, ... — on one `Conversation`."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    conversation_id: UUID
    event_type: str
    metadata: dict[str, Any] = {}
    occurred_at: datetime
    created_at: datetime

    @field_validator("event_type")
    @classmethod
    def _event_type_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ConversationEvent event_type must not be blank.")
        return value
