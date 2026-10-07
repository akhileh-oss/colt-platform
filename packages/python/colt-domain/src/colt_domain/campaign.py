"""The Campaign entity (CLAUDE.md §10.9) — targeting, sequence, channels, limits and approval
policy for an outbound motion.

`CampaignStatus` is a closed state machine added in Milestone 14 — CLAUDE.md §11 never defines
one for campaigns (unlike Lead, Conversation and Opportunity), so this milestone's own Build
list item ("campaign state machine") and acceptance criterion ("can be created, validated,
paused, resumed, and inspected") are the specification: a documented design decision, not a
guess left unstated. `colt_application.campaign_state` holds the actual transition rules and
validation logic (§2.1: deterministic business logic belongs in the application layer, not the
entity itself).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CampaignStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class Campaign(BaseModel):
    """One organization's configured outbound campaign."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    #: `max_length` (CLAUDE.md §40's "input validation"/"request size limits", Milestone 24),
    #: matching `CampaignModel.name`'s own `String(300)` column exactly — the domain layer must
    #: never claim a looser bound than the database actually enforces.
    name: str = Field(max_length=300)
    status: CampaignStatus = CampaignStatus.DRAFT
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
