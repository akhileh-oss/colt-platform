"""The `users` table (CLAUDE.md §10.2)."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from colt_db.base import Base, IdentityMixin, TimestampMixin
from colt_domain import Role, UserStatus

_VALID_STATUSES = tuple(s.value for s in UserStatus)
_VALID_ROLES = tuple(r.value for r in Role)


class UserModel(IdentityMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # A given identity-provider subject maps to exactly one Colt user (ADR-0005): the
        # lookup that resolves organization context depends on this being unique.
        UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),
        UniqueConstraint("organization_id", "email", name="uq_users_organization_email"),
        CheckConstraint(f"status IN {_VALID_STATUSES}", name="valid_status"),
        CheckConstraint(f"role IN {_VALID_ROLES}", name="valid_role"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_auth_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")
