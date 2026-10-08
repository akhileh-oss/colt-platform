"""The Message entity (CLAUDE.md §10.11) — a drafted or sent outbound message.

`idempotency_key` exists so a retried send workflow (§2.9, §24.4) can never double-send: the
database enforces uniqueness on it, this model just carries the value through.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Message(BaseModel):
    """One drafted or sent outbound message within a campaign, addressed to one lead."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    campaign_id: UUID
    lead_id: UUID
    conversation_id: UUID | None = None
    sequence_step_id: UUID | None = None
    channel: str
    #: `max_length` on `subject`/`body` (CLAUDE.md §40, Milestone 24). `subject` matches
    #: `MessageModel.subject`'s own `String(500)` column exactly. `body` backs onto an unbounded
    #: `Text` column, so its own bound is a deliberately tighter app-level cap, not a DB-matched
    #: one — generous enough for any real email, but never unbounded.
    subject: str | None = Field(default=None, max_length=500)
    body: str = Field(max_length=100_000)
    status: str = "DRAFT"
    approval_status: str = "PENDING"
    evidence_ids: list[UUID] = []
    model_name: str | None = None
    prompt_version: str | None = None
    idempotency_key: str | None = None
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    provider_message_id: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("channel")
    @classmethod
    def _channel_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message channel must not be blank.")
        return value

    @field_validator("body")
    @classmethod
    def _body_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message body must not be blank.")
        return value
