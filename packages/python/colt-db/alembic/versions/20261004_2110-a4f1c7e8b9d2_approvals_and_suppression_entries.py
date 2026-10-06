"""approvals and suppression entries

Revision ID: a4f1c7e8b9d2
Revises: 3b9c1dbe395e
Create Date: 2026-10-04 21:10:00.000000

CLAUDE.md §10.17 (`Approval`) and §10.18 (`SuppressionEntry`), Milestone 16's two new entities.

`approvals` carries `organization_id` and gets the usual Row-Level Security treatment (§9.7,
§27, ADR-0005) — a plain tenant-owned table, no different from `sequence_steps` before it.

`suppression_entries` is not plain: §10.18 itself says `organization_id` is "nullable for
system-wide policy", and §18.1 says "no campaign or agent may override a suppression entry."
The usual `tenant_isolation` policy (`organization_id = current_setting(...)`) would make a
NULL-organization row invisible to every tenant, which is the opposite of what a system-wide
suppression is for. This migration's policy is `organization_id = current_setting(...) OR
organization_id IS NULL` instead — a deliberate, documented departure from the usual RLS
pattern, made once here rather than silently reusing a policy that would quietly defeat the
entity's own stated purpose.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4f1c7e8b9d2"
down_revision: str | Sequence[str] | None = "3b9c1dbe395e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
            name=op.f("fk_approvals_approved_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_approvals_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_approvals_requested_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approvals")),
    )
    op.create_index(op.f("ix_approvals_entity_id"), "approvals", ["entity_id"], unique=False)
    op.create_index(op.f("ix_approvals_entity_type"), "approvals", ["entity_type"], unique=False)
    op.create_index(
        op.f("ix_approvals_organization_id"), "approvals", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_approvals_status"), "approvals", ["status"], unique=False)

    op.execute("ALTER TABLE approvals ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE approvals FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON approvals
        USING (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        """
    )

    op.create_table(
        "suppression_entries",
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("identifier_type", sa.String(length=50), nullable=False),
        sa.Column("identifier", sa.String(length=320), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
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
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_suppression_entries_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suppression_entries")),
        sa.UniqueConstraint(
            "organization_id",
            "identifier_type",
            "identifier",
            name="uq_suppression_entries_org_identifier",
        ),
    )
    op.create_index(
        op.f("ix_suppression_entries_identifier"),
        "suppression_entries",
        ["identifier"],
        unique=False,
    )
    op.create_index(
        op.f("ix_suppression_entries_identifier_type"),
        "suppression_entries",
        ["identifier_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_suppression_entries_organization_id"),
        "suppression_entries",
        ["organization_id"],
        unique=False,
    )

    op.execute("ALTER TABLE suppression_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE suppression_entries FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON suppression_entries
        USING (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
            OR organization_id IS NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON suppression_entries")
    op.drop_index(op.f("ix_suppression_entries_organization_id"), table_name="suppression_entries")
    op.drop_index(op.f("ix_suppression_entries_identifier_type"), table_name="suppression_entries")
    op.drop_index(op.f("ix_suppression_entries_identifier"), table_name="suppression_entries")
    op.drop_table("suppression_entries")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON approvals")
    op.drop_index(op.f("ix_approvals_status"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_organization_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_entity_type"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_entity_id"), table_name="approvals")
    op.drop_table("approvals")
