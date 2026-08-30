"""The `organizations` table (CLAUDE.md §10.1)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin

_VALID_STATUSES = ("ACTIVE", "SUSPENDED", "ARCHIVED")


class OrganizationModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (CheckConstraint(f"status IN {_VALID_STATUSES}", name="valid_status"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
