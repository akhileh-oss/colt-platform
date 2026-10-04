"""The `lead_scores` table (CLAUDE.md §10.8) — append-only; no `updated_at`, no update path."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, TIMESTAMP, CheckConstraint, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin

_UNIT_RANGE_COLUMNS = (
    "icp_fit",
    "persona_fit",
    "signal_strength",
    "timing",
    "model_assessment",
    "overall_score",
)


class LeadScoreModel(IdentityMixin, Base):
    __tablename__ = "lead_scores"
    __table_args__ = (
        *(
            CheckConstraint(f"{column} >= 0 AND {column} <= 1", name=f"valid_{column}")
            for column in _UNIT_RANGE_COLUMNS
        ),
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
    lead_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    icp_fit: Mapped[float] = mapped_column(Float, nullable=False)
    persona_fit: Mapped[float] = mapped_column(Float, nullable=False)
    signal_strength: Mapped[float] = mapped_column(Float, nullable=False)
    timing: Mapped[float] = mapped_column(Float, nullable=False)
    model_assessment: Mapped[float] = mapped_column(Float, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(ARRAY(String(50)), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
