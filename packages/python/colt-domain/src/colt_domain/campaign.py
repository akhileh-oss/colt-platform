"""The Campaign entity (CLAUDE.md §10.9) — targeting, sequence, channels, limits and approval
policy for an outbound motion.

`status` is a plain string with an application-level default, not a closed enum: unlike Lead,
Conversation and Opportunity, CLAUDE.md §11 does not define a campaign state machine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class Campaign(BaseModel):
    """One organization's configured outbound campaign."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    name: str
    status: str = "DRAFT"
    objective: str | None = None
    icp_definition: dict[str, Any] = {}
    rules: dict[str, Any] = {}
    channels: list[str] = []
    schedule: dict[str, Any] = {}
    limits: dict[str, Any] = {}
    approval_policy: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Campaign name must not be blank.")
        return value
