"""The `crm_sync_records` table (CLAUDE.md §30)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin
from colt_domain import SyncStatus

_VALID_STATUSES = tuple(s.value for s in SyncStatus)


class CrmSyncRecordModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "crm_sync_records"
    __table_args__ = (
        CheckConstraint(f"sync_status IN {_VALID_STATUSES}", name="valid_sync_status"),
        # One sync record per (entity, provider) — a second sync of the same entity updates
        # this row rather than creating a duplicate mapping to the same CRM provider.
        UniqueConstraint(
            "organization_id",
            "entity_type",
            "entity_id",
            "provider_name",
            name="uq_crm_sync_target",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_object_id: Mapped[str | None] = mapped_column(String(255))
    sync_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=SyncStatus.PENDING.value
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String())
