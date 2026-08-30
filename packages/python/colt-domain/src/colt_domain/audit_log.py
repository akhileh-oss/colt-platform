"""The AuditLog entity (CLAUDE.md §48) — an append-only record of a sensitive action.

No `updated_at`, unlike most entities in this package: an audit record is written once and never
mutated (§9.4, §48 — "append-only from the application's perspective").
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class AuditLog(BaseModel):
    """One recorded sensitive action — a login, a campaign launch, a message send, ..."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    actor_type: str
    actor_id: UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    metadata: dict[str, Any] = {}
    created_at: datetime
    request_id: str | None = None
    trace_id: str | None = None

    @field_validator("actor_type")
    @classmethod
    def _actor_type_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("actor_type must not be blank.")
        return value

    @field_validator("action")
    @classmethod
    def _action_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("action must not be blank.")
        return value
