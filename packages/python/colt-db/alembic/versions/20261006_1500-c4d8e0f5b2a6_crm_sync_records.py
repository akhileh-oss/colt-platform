"""crm sync records

Revision ID: c4d8e0f5b2a6
Revises: b7c3d9e4a1f5
Create Date: 2026-10-06 15:00:00.000000

CLAUDE.md §30 (Milestone 20, CRM Integration) names the fields to persist (provider name,
provider account ID, provider object ID, last synced at, sync status, last error) for the one
row that tracks how a Colt entity maps to an external CRM object. Polymorphic (`entity_type` +
`entity_id`) for the same reason `evidence` (Milestone 02) is: any syncable entity can be the
subject without a table per entity type.

Plain tenant-owned table, RLS enabled/forced with the usual `tenant_isolation` policy — no
departure from the standard pattern.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8e0f5b2a6"
down_revision: str | Sequence[str] | None = "b7c3d9e4a1f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crm_sync_records",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("provider_name", sa.String(length=50), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("provider_object_id", sa.String(length=255), nullable=True),
        sa.Column("sync_status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("last_synced_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
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
        sa.CheckConstraint(
            "sync_status IN ('PENDING', 'SYNCED', 'FAILED')",
            name=op.f("ck_crm_sync_records_valid_sync_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_crm_sync_records_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_sync_records")),
        sa.UniqueConstraint(
            "organization_id",
            "entity_type",
            "entity_id",
            "provider_name",
            name="uq_crm_sync_target",
        ),
    )
    op.create_index(
        op.f("ix_crm_sync_records_entity_id"), "crm_sync_records", ["entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_crm_sync_records_entity_type"), "crm_sync_records", ["entity_type"], unique=False
    )
    op.create_index(
        op.f("ix_crm_sync_records_organization_id"),
        "crm_sync_records",
        ["organization_id"],
        unique=False,
    )

    op.execute("ALTER TABLE crm_sync_records ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE crm_sync_records FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON crm_sync_records
        USING (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON crm_sync_records")
    op.drop_index(op.f("ix_crm_sync_records_organization_id"), table_name="crm_sync_records")
    op.drop_index(op.f("ix_crm_sync_records_entity_type"), table_name="crm_sync_records")
    op.drop_index(op.f("ix_crm_sync_records_entity_id"), table_name="crm_sync_records")
    op.drop_table("crm_sync_records")
