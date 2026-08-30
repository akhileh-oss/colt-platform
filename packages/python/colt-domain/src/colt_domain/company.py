"""The Company entity (CLAUDE.md §10.3) — a prospect company."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class Company(BaseModel):
    """A prospect company within one organization's account."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    name: str
    domain: str | None = None
    normalized_domain: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    revenue_range: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    description: str | None = None
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
