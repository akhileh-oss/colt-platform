"""The `signals` table (CLAUDE.md §10.5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, CheckConstraint, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin


class SignalModel(IdentityMixin, Base):
    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="valid_confidence",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id", ondelete="CASCADE"), index=True
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    source_type: Mapped[str | None] = mapped_column(String(50))
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    event_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    confidence: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
