"""lead scores

Revision ID: 7e2860cacfda
Revises: f613444d92f9
Create Date: 2026-10-04 13:49:00.304437

`lead_scores` carries `organization_id` and gets the same Row-Level Security treatment every
tenant-owned table does (CLAUDE.md §9.7, §27, ADR-0005). CLAUDE.md §10.8 is explicit that
scoring history must never be overwritten ("Do not overwrite scoring history. Use immutable or
append-only score evaluations where practical.") - there is no `updated_at` column and no
update path, only `add()`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7e2860cacfda"
down_revision: str | Sequence[str] | None = "f613444d92f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UNIT_RANGE_COLUMNS = (
    "icp_fit",
    "persona_fit",
    "signal_strength",
    "timing",
    "model_assessment",
    "overall_score",
)


def upgrade() -> None:
    op.create_table(
        "lead_scores",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("icp_fit", sa.Float(), nullable=False),
        sa.Column("persona_fit", sa.Float(), nullable=False),
        sa.Column("signal_strength", sa.Float(), nullable=False),
        sa.Column("timing", sa.Float(), nullable=False),
        sa.Column("model_assessment", sa.Float(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("reason_codes", postgresql.ARRAY(sa.String(length=50)), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        *(
            sa.CheckConstraint(
                f"{column} >= 0 AND {column} <= 1", name=op.f(f"ck_lead_scores_valid_{column}")
            )
            for column in _UNIT_RANGE_COLUMNS
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_lead_scores_valid_confidence"),
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_scores_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_lead_scores_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_scores")),
    )
    op.create_index(op.f("ix_lead_scores_lead_id"), "lead_scores", ["lead_id"], unique=False)
    op.create_index(
        op.f("ix_lead_scores_organization_id"), "lead_scores", ["organization_id"], unique=False
    )

    op.execute("ALTER TABLE lead_scores ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lead_scores FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON lead_scores
        USING (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON lead_scores")
    op.drop_index(op.f("ix_lead_scores_organization_id"), table_name="lead_scores")
    op.drop_index(op.f("ix_lead_scores_lead_id"), table_name="lead_scores")
    op.drop_table("lead_scores")
