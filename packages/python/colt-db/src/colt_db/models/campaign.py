"""The `campaigns` table (CLAUDE.md §10.9)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin


class CampaignModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="DRAFT", index=True
    )
    objective: Mapped[str | None] = mapped_column(Text)
    icp_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    channels: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    schedule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    limits: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    approval_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
