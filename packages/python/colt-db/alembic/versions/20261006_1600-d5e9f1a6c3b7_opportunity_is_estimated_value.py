"""opportunity is_estimated_value

Revision ID: d5e9f1a6c3b7
Revises: c4d8e0f5b2a6
Create Date: 2026-10-06 16:00:00.000000

CLAUDE.md §12.11 (`OpportunityAgent`, Milestone 21): "must not invent deal value unless
configured source/rules permit an estimate. Estimates must be labeled estimates." No configured
override source exists in this environment, so every model-supplied `estimated_value` is always
an estimate — this column is where that label is recorded, rather than needing a schema change
once such a source does exist.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e9f1a6c3b7"
down_revision: str | Sequence[str] | None = "c4d8e0f5b2a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "opportunities",
        sa.Column("is_estimated_value", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("opportunities", "is_estimated_value")
