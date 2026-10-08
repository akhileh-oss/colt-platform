"""The Company entity (CLAUDE.md §10.3) — a prospect company."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Company(BaseModel):
    """A prospect company within one organization's account."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    #: `max_length` on `name` (CLAUDE.md §40, Milestone 24), matching `CompanyModel.name`'s own
    #: `String(300)` column exactly. `description` backs onto an unbounded `Text` column, so its
    #: own bound below is a deliberately tighter app-level cap, not a DB-matched one — a hostile
    #: or malformed source document must never grow a single row without limit.
    name: str = Field(max_length=300)
    domain: str | None = None
    normalized_domain: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    revenue_range: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    description: str | None = Field(default=None, max_length=5_000)
    website_url: str | None = None
    linkedin_url: str | None = None
    source_metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Company name must not be blank.")
        return value

    @field_validator("employee_count")
    @classmethod
    def _employee_count_not_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("employee_count must not be negative.")
        return value
