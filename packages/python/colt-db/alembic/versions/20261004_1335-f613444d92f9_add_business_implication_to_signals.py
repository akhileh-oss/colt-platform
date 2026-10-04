"""add business_implication to signals

Revision ID: f613444d92f9
Revises: 2a5e592b6a86
Create Date: 2026-10-04 13:35:44.289727

CLAUDE.md §12.6 requires `SignalAgent`'s output to include `business_implication` — judgment
about what a signal means for sales strategy, not a deterministic computation (§2.1), so
unlike `verification_status`/`email_status` this is never server-computed and needs no `CHECK`
constraint, just a nullable text column `SignalAgent` is the first thing to populate.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f613444d92f9"
down_revision: str | Sequence[str] | None = "2a5e592b6a86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("signals", sa.Column("business_implication", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("signals", "business_implication")
