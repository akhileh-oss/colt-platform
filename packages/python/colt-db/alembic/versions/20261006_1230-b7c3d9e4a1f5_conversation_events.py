"""conversation events

Revision ID: b7c3d9e4a1f5
Revises: a4f1c7e8b9d2
Create Date: 2026-10-06 12:30:00.000000

CLAUDE.md §10.13 defines `ConversationEvent`, but no prior milestone's Build list named it as a
deliverable; Milestone 17's inbound email processing is the first thing that actually needs an
append-only timeline on a `Conversation` to write to.

Plain tenant-owned table, RLS enabled/forced with the usual `tenant_isolation` policy — no
departure from the standard pattern the way `suppression_entries` needed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c3d9e4a1f5"
down_revision: str | Sequence[str] | None = "a4f1c7e8b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_events",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_conversation_events_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_conversation_events_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_events")),
    )
    op.create_index(
        op.f("ix_conversation_events_conversation_id"),
        "conversation_events",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_events_event_type"),
        "conversation_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_events_organization_id"),
        "conversation_events",
        ["organization_id"],
        unique=False,
    )

    op.execute("ALTER TABLE conversation_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversation_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON conversation_events
        USING (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON conversation_events")
    op.drop_index(op.f("ix_conversation_events_organization_id"), table_name="conversation_events")
    op.drop_index(op.f("ix_conversation_events_event_type"), table_name="conversation_events")
    op.drop_index(op.f("ix_conversation_events_conversation_id"), table_name="conversation_events")
    op.drop_table("conversation_events")
