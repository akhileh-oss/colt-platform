"""The `opportunities` table (CLAUDE.md §10.14)."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin
from colt_domain import PipelineStage

_VALID_STAGES = tuple(s.value for s in PipelineStage)


class OpportunityModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(f"pipeline_stage IN {_VALID_STAGES}", name="valid_pipeline_stage"),
        CheckConstraint(
            "probability IS NULL OR (probability >= 0 AND probability <= 1)",
            name="valid_probability",
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
    primary_person_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL"), index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), index=True
    )
    pipeline_stage: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=PipelineStage.QUALIFIED.value, index=True
    )
    estimated_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    probability: Mapped[float | None] = mapped_column(Numeric(4, 3))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[str | None] = mapped_column(String(100))
