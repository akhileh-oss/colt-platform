"""The `sequence_steps` table (CLAUDE.md §10.10)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin


class SequenceStepModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "sequence_steps"
    __table_args__ = (
        # Two steps of the same campaign can't both claim the same position in the sequence.
        UniqueConstraint("campaign_id", "step_order", name="uq_sequence_steps_campaign_order"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    delay_after_previous: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    message_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
