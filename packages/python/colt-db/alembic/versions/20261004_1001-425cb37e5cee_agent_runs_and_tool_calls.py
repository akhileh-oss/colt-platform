"""agent runs and tool calls

Revision ID: 425cb37e5cee
Revises: a2d24a5f5578
Create Date: 2026-10-04 10:01:26.246805

Both tables carry `organization_id` and get the same Row-Level Security treatment every
tenant-owned table does (CLAUDE.md §9.7, §27, ADR-0005): ENABLE + FORCE ROW LEVEL SECURITY, and
a `tenant_isolation` policy keyed to `app.current_organization_id`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "425cb37e5cee"
down_revision: str | Sequence[str] | None = "a2d24a5f5578"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_TABLES = ("agent_runs", "tool_calls")


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table}
        USING (
            organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid
        )
        """
    )


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("agent_version", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("workflow_id", sa.String(length=255), nullable=True),
        sa.Column("workflow_run_id", sa.String(length=255), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="RUNNING", nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tool_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name=op.f("ck_agent_runs_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_agent_runs_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index(op.f("ix_agent_runs_agent_name"), "agent_runs", ["agent_name"], unique=False)
    op.create_index(op.f("ix_agent_runs_entity_id"), "agent_runs", ["entity_id"], unique=False)
    op.create_index(
        op.f("ix_agent_runs_organization_id"), "agent_runs", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"], unique=False)

    op.create_table(
        "tool_calls",
        sa.Column("agent_run_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("tool_version", sa.String(length=50), nullable=False),
        sa.Column("arguments_redacted", sa.Text(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="RUNNING", nullable=False),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED')",
            name=op.f("ck_tool_calls_valid_status"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.id"],
            name=op.f("fk_tool_calls_agent_run_id_agent_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_tool_calls_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_calls")),
    )
    op.create_index(
        op.f("ix_tool_calls_agent_run_id"), "tool_calls", ["agent_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_tool_calls_organization_id"), "tool_calls", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_tool_calls_status"), "tool_calls", ["status"], unique=False)
    op.create_index(op.f("ix_tool_calls_tool_name"), "tool_calls", ["tool_name"], unique=False)

    for table in _TENANT_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_index(op.f("ix_tool_calls_tool_name"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_status"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_organization_id"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_agent_run_id"), table_name="tool_calls")
    op.drop_table("tool_calls")

    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_organization_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_entity_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_name"), table_name="agent_runs")
    op.drop_table("agent_runs")
