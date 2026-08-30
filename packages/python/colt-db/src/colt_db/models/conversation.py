"""The `conversations` table (CLAUDE.md §10.12)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin
from colt_domain import ConversationState

_VALID_STATES = tuple(s.value for s in ConversationState)


class ConversationModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (CheckConstraint(f"state IN {_VALID_STATES}", name="valid_state"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=ConversationState.OPEN.value, index=True
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
