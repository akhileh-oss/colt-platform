"""The `audit_logs` table (CLAUDE.md §48).

No `updated_at` and no application update path: an audit record is append-only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin


class AuditLogModel(IdentityMixin, Base):
    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    #: No foreign key — polymorphic (a User, a service identity, "system"); the actor may no
    #: longer exist and the audit record must still be readable.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), index=True)
    #: Named `audit_metadata` in Python — `metadata` is reserved on every Declarative model (it's
    #: `Base.metadata`, the schema object) — but stored as the `metadata` column CLAUDE.md §48
    #: specifies.
    audit_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    request_id: Mapped[str | None] = mapped_column(String(100))
    trace_id: Mapped[str | None] = mapped_column(String(100))
