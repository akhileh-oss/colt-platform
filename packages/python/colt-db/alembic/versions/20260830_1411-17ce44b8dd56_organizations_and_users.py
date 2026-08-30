"""organizations and users

Revision ID: 17ce44b8dd56
Revises:
Create Date: 2026-08-30 14:11:25.607886

Row-Level Security (CLAUDE.md §9.7, ADR-0005): `users` is enabled and FORCED, meaning RLS
applies even to the table's owning role — without FORCE, PostgreSQL exempts the owner by
default and the policy below would silently do nothing against the very role Colt connects as.

The policy allows a row when either:
  * `app.current_organization_id` (set once per request/transaction by
    `colt_db.tenancy.set_tenant_context`) matches the row's organization_id, or
  * `app.bypass_rls` is set to 'true' — used by exactly one code path,
    `SqlAlchemyUserDirectory.find_by_external_auth_id`, which resolves a verified identity to
    its organization *before* an organization_id is known. That is the one lookup RLS cannot
    itself gate on organization, so it is named and narrow rather than left as an owner-bypass
    nobody documented.

`organizations` has no RLS: it is the tenancy root, has no organization_id of its own to filter
by, and a session touches at most the one row context resolution already found.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "17ce44b8dd56"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column(
            "settings", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'ARCHIVED')",
            name=op.f("ck_organizations_valid_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("external_auth_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN "
            "('OWNER', 'ADMIN', 'MANAGER', 'SALES', 'MARKETING', 'VIEWER', 'SERVICE_AGENT')",
            name=op.f("ck_users_valid_role"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INVITED', 'SUSPENDED', 'DEACTIVATED')",
            name=op.f("ck_users_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_users_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),
        sa.UniqueConstraint("organization_id", "email", name="uq_users_organization_email"),
    )
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False)

    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON users
        USING (
            COALESCE(current_setting('app.bypass_rls', true), 'false') = 'true'
            OR organization_id
                = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.drop_index(op.f("ix_users_organization_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_table("organizations")
