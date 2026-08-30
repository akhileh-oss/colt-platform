"""The Lead entity (CLAUDE.md §10.7) — a relationship-oriented prospect record.

`LeadStatus` is the closed state machine from §11.1: models may not invent a status outside this
set. The linear progression (NEW → ... → ENGAGED) and the terminal/branching states are both
valid values of the same field — there is no separate "terminal" type — so transitions are
enforced by application code, not by the enum itself.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LeadStatus(StrEnum):
    NEW = "NEW"
    DISCOVERED = "DISCOVERED"
    ENRICHING = "ENRICHING"
    RESEARCHED = "RESEARCHED"
    QUALIFIED = "QUALIFIED"
    PERSONALIZED = "PERSONALIZED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    READY = "READY"
    CONTACTED = "CONTACTED"
    ENGAGED = "ENGAGED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    NOT_INTERESTED = "NOT_INTERESTED"
    UNSUBSCRIBED = "UNSUBSCRIBED"
    SUPPRESSED = "SUPPRESSED"
    NURTURE = "NURTURE"
    CONVERTED = "CONVERTED"


class Lead(BaseModel):
    """A relationship-oriented prospect record tying one `Person` at one `Company` into the
    funnel."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    company_id: UUID
    person_id: UUID
    status: LeadStatus = LeadStatus.NEW
    source: str | None = None
    current_stage: str | None = None
    priority: str | None = None
    created_at: datetime
    updated_at: datetime

    def with_status(self, status: LeadStatus, *, at: datetime) -> Self:
        return self.model_copy(update={"status": status, "updated_at": at})
