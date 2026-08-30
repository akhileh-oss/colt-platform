"""The Organization entity (CLAUDE.md §10.1) — the tenancy root.

Pure domain model: no ORM, no FastAPI, no I/O (CLAUDE.md §5.3). ``colt-db`` maps this to and
from a SQLAlchemy row; this module knows nothing about that mapping.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

#: Lowercase, alphanumeric with single hyphens, no leading/trailing hyphen. Used in URLs and as
#: a human-referenceable identifier, so it is validated at the domain boundary rather than left
#: to whatever happens to write it to the database.
_SLUG_PATTERN = re.compile(r"\A[a-z0-9]+(-[a-z0-9]+)*\Z")


class OrganizationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class Organization(BaseModel):
    """A Colt customer/workspace — the root every tenant-owned record scopes to."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    slug: str
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    settings: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Organization name must not be blank.")
        return value

    @field_validator("slug")
    @classmethod
    def _slug_is_url_safe(cls, value: str) -> str:
        if not _SLUG_PATTERN.fullmatch(value):
            raise ValueError(
                "Organization slug must be lowercase alphanumeric segments joined by single "
                f"hyphens (e.g. 'acme-corp'); got {value!r}."
            )
        return value

    @property
    def is_active(self) -> bool:
        return self.status is OrganizationStatus.ACTIVE

    def with_status(self, status: OrganizationStatus, *, at: datetime) -> Self:
        """Return a copy with a new status. The entity is frozen; this never mutates in place."""
        return self.model_copy(update={"status": status, "updated_at": at})
