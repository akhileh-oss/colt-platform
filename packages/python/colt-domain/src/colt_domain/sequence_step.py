"""The Sequence step entity (CLAUDE.md §10.10) — one ordered step of a Campaign's outbound
sequence.

CLAUDE.md's own schema listing for this entity names no `organization_id`, `created_at` or
`updated_at` — but every other tenant-owned entity in this codebase carries `organization_id`
for direct Row-Level Security (§9.7, §27, ADR-0005) regardless of whether its own §10.x listing
spells it out (`Signal`, `Evidence`, `Campaign` itself all do), and `active` is a field this
entity's own schema says is meant to be toggled after creation — so, consistent with `Campaign`'s
own `TimestampMixin` and every other mutable tenant table, this adds `created_at`/`updated_at`
too. A documented extension of the literal schema, not a guess left unstated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class SequenceStep(BaseModel):
    """One ordered step of a `Campaign`'s outbound sequence."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    campaign_id: UUID
    step_order: int
    channel: str
    #: Minutes to wait after the previous step (or after campaign activation, for the first
    #: step) before this step becomes eligible to run.
    delay_after_previous: int = 0
    message_strategy: str
    conditions: dict[str, Any] = {}
    active: bool = True
    created_at: datetime
    updated_at: datetime

    @field_validator("channel")
    @classmethod
    def _channel_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Sequence step channel must not be blank.")
        return value

    @field_validator("message_strategy")
    @classmethod
    def _message_strategy_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Sequence step message_strategy must not be blank.")
        return value

    @field_validator("step_order")
    @classmethod
    def _step_order_not_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Sequence step step_order must not be negative.")
        return value

    @field_validator("delay_after_previous")
    @classmethod
    def _delay_not_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Sequence step delay_after_previous must not be negative.")
        return value
