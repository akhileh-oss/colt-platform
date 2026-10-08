"""The Person entity (CLAUDE.md §10.4) — a contact at a prospect company.

`EmailStatus` is a closed set (Milestone 11, CLAUDE.md §16.1's `verify_email` tool category) —
Milestone 05 left `email_status` a plain string because nothing yet computed anything beyond
`None`; Milestone 11's `EnrichmentAgent` is the first thing that actually sets it.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmailStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VALID = "VALID"
    INVALID = "INVALID"
    RISKY = "RISKY"
    UNKNOWN = "UNKNOWN"


class Person(BaseModel):
    """A contact at a `Company`, within one organization's account."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    company_id: UUID
    first_name: str | None = None
    last_name: str | None = None
    #: `max_length` (CLAUDE.md §40, Milestone 24), matching `PersonModel.full_name`'s own
    #: `String(300)` column exactly.
    full_name: str = Field(max_length=300)
    title: str | None = None
    seniority: str | None = None
    department: str | None = None
    email: str | None = None
    email_status: EmailStatus | None = None
    linkedin_url: str | None = None
    location: str | None = None
    source_metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    @field_validator("full_name")
    @classmethod
    def _full_name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Person full_name must not be blank.")
        return value
