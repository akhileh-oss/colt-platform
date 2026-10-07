"""The `people` table (CLAUDE.md §10.4)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin
from colt_domain import EmailStatus

_VALID_EMAIL_STATUSES = tuple(s.value for s in EmailStatus)


class PersonModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "people"
    __table_args__ = (
        CheckConstraint(
            f"email_status IS NULL OR email_status IN {_VALID_EMAIL_STATUSES}",
            name="valid_email_status",
        ),
        # Milestone 27: `DiscoverPerson`'s check-then-insert dedup is otherwise a real race
        # under concurrency, the same finding as `CompanyModel.normalized_domain`'s own index
        # above. Partial because `email` is nullable and multiple people with no known email
        # must coexist.
        Index(
            "uq_people_org_email",
            "organization_id",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
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
    first_name: Mapped[str | None] = mapped_column(String(150))
    last_name: Mapped[str | None] = mapped_column(String(150))
    full_name: Mapped[str] = mapped_column(String(300), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    seniority: Mapped[str | None] = mapped_column(String(50))
    department: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    email_status: Mapped[str | None] = mapped_column(String(50))
    linkedin_url: Mapped[str | None] = mapped_column(String(2048))
    location: Mapped[str | None] = mapped_column(String(200))
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
