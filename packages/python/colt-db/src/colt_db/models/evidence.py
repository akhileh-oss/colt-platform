"""The `evidence` table (CLAUDE.md §10.6)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import TIMESTAMP, CheckConstraint, Date, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin
from colt_domain import VerificationStatus

_VALID_VERIFICATION_STATUSES = tuple(s.value for s in VerificationStatus)


class EvidenceModel(IdentityMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="valid_confidence",
        ),
        CheckConstraint(
            f"verification_status IN {_VALID_VERIFICATION_STATUSES}",
            name="valid_verification_status",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Polymorphic reference (a Company, Signal, Lead, ...) — no foreign key, since evidence can
    #: attach to any evidence-bearing entity.
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(50))
    source_date: Mapped[date | None] = mapped_column(Date)
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    verification_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=VerificationStatus.UNVERIFIED.value
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
