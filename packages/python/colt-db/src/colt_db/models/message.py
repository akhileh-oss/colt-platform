"""The `messages` table (CLAUDE.md §10.11).

`sequence_step_id` has no foreign key: `sequence_steps` is a Milestone 14 (Campaign Engine)
table, out of scope for Milestone 05's domain foundation. The column exists now so Milestone 14
adds only a constraint, not a migration that reshapes rows already in production.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin


class MessageModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        # Partial unique indexes: both keys are optional (a draft has neither yet), but once
        # present must be unique per organization — enforcing idempotent send (§2.9, §24.4)
        # and a one-to-one link to the provider's own message record.
        Index(
            "uq_messages_organization_idempotency_key",
            "organization_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "uq_messages_organization_provider_message_id",
            "organization_id",
            "provider_message_id",
            unique=True,
            postgresql_where=text("provider_message_id IS NOT NULL"),
        ),
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
    lead_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), index=True
    )
    sequence_step_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="DRAFT", index=True
    )
    approval_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="PENDING"
    )
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    scheduled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
