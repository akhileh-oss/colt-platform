"""The `companies` table (CLAUDE.md §10.3)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin


class CompanyModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        # Milestone 27: `DiscoverCompany`'s check-then-insert dedup is otherwise a real race
        # under concurrency (two discoveries of the same company at once can both pass the
        # "does it exist" check before either commits) — a real, disposable-Postgres-proven
        # duplicate, not a hypothetical one. Partial (not a plain unique column) because
        # `normalized_domain` is nullable and multiple companies with no known domain must
        # coexist.
        Index(
            "uq_companies_org_normalized_domain",
            "organization_id",
            "normalized_domain",
            unique=True,
            postgresql_where=text("normalized_domain IS NOT NULL"),
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255))
    normalized_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    industry: Mapped[str | None] = mapped_column(String(200))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    revenue_range: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(String(2048))
    linkedin_url: Mapped[str | None] = mapped_column(String(2048))
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
