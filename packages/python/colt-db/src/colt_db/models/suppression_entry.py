"""The `suppression_entries` table (CLAUDE.md §10.18, §18.1) — explicit, global outbound
suppression. `organization_id` is nullable "for system-wide policy", per §10.18 itself; see this
milestone's Alembic migration for how Row-Level Security is adapted to let a NULL-organization
row remain visible to every tenant rather than becoming invisible to all of them.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin


class SuppressionEntryModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "suppression_entries"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "identifier_type",
            "identifier",
            name="uq_suppression_entries_org_identifier",
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    identifier: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
