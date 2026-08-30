"""The `leads` table (CLAUDE.md §10.7)."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin
from colt_domain import LeadStatus

_VALID_STATUSES = tuple(s.value for s in LeadStatus)


class LeadModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        # One lead per person per organization — re-discovering the same person doesn't create
        # a second funnel entry.
        UniqueConstraint("organization_id", "person_id", name="uq_leads_organization_person"),
        CheckConstraint(f"status IN {_VALID_STATUSES}", name="valid_status"),
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
    person_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=LeadStatus.NEW.value, index=True
    )
    source: Mapped[str | None] = mapped_column(String(100))
    current_stage: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[str | None] = mapped_column(String(20))
