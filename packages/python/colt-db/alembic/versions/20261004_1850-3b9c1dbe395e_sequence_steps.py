"""sequence steps

Revision ID: 3b9c1dbe395e
Revises: ec125daa3d18
Create Date: 2026-10-04 18:50:00.000000

CLAUDE.md §10.10 defines a `SequenceStep` entity and Milestone 14's own Build list names
"sequence steps" as its own deliverable, separate from Campaign's `channels` list — a gap this
migration closes within the same milestone, not deferred to a later one.

`sequence_steps` carries `organization_id` and gets the same Row-Level Security treatment every
tenant-owned table does (CLAUDE.md §9.7, §27, ADR-0005), even though §10.10's own field listing
doesn't spell it out. `(campaign_id, step_order)` is unique: two steps of the same campaign
can't both claim the same position in the sequence.

`messages.sequence_step_id` has carried no foreign key since Milestone 05, by design — its own
model docstring says so explicitly: "The column exists now so Milestone 14 adds only a
constraint, not a migration that reshapes rows already in production." This migration adds
that promised constraint. `ON DELETE SET NULL`, not `CASCADE`: a message that was already sent
must not disappear just because its originating sequence step was later removed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3b9c1dbe395e"
down_revision: str | Sequence[str] | None = "ec125daa3d18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sequence_steps",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("delay_after_previous", sa.Integer(), server_default="0", nullable=False),
        sa.Column("message_strategy", sa.Text(), nullable=False),
        sa.Column("conditions", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
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
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_sequence_steps_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_sequence_steps_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sequence_steps")),
        sa.UniqueConstraint("campaign_id", "step_order", name="uq_sequence_steps_campaign_order"),
    )
    op.create_index(
        op.f("ix_sequence_steps_campaign_id"), "sequence_steps", ["campaign_id"], unique=False
    )
    op.create_index(
        op.f("ix_sequence_steps_organization_id"),
        "sequence_steps",
        ["organization_id"],
        unique=False,
    )

    op.execute("ALTER TABLE sequence_steps ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sequence_steps FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON sequence_steps
        USING (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        """
    )

    op.create_foreign_key(
        op.f("fk_messages_sequence_step_id_sequence_steps"),
        "messages",
        "sequence_steps",
        ["sequence_step_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_messages_sequence_step_id_sequence_steps"), "messages", type_="foreignkey"
    )
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON sequence_steps")
    op.drop_index(op.f("ix_sequence_steps_organization_id"), table_name="sequence_steps")
    op.drop_index(op.f("ix_sequence_steps_campaign_id"), table_name="sequence_steps")
    op.drop_table("sequence_steps")
