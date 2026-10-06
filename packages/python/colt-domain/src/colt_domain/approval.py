"""The Approval entity (CLAUDE.md §10.17) — a human decision on a sensitive, gated action.

`ApprovalStatus` is a closed set, the same reasoning §11's "do not let LLMs invent arbitrary
statuses" applies to any status this codebase checks deterministically, not only the three
entities §11 names by number. `decided_by`/`decided_at`/`reason` are unset until a decision is
made — `Approval` always starts `PENDING`, the same pattern `Campaign` always starting `DRAFT`
established in Milestone 14.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Approval(BaseModel):
    """One requested, and possibly decided, approval for a gated action on an entity."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    entity_type: str
    entity_id: UUID
    action_type: str
    requested_by: UUID | None = None
    approved_by: UUID | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: str | None = None
    created_at: datetime
    decided_at: datetime | None = None

    @field_validator("entity_type", "action_type")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Approval entity_type and action_type must not be blank.")
        return value
