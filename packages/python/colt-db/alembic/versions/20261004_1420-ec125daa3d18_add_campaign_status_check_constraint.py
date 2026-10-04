"""add campaign status check constraint

Revision ID: ec125daa3d18
Revises: 7e2860cacfda
Create Date: 2026-10-04 14:20:00.000000

Milestone 05 left `campaigns.status` an open string since nothing yet enforced a state
machine. Milestone 14 adds one (`colt_domain.campaign.CampaignStatus`: DRAFT/ACTIVE/PAUSED/
COMPLETED/ARCHIVED — CLAUDE.md §11 never defines a campaign state machine, so this is this
milestone's own documented design decision), so this retrofits the same `CHECK` constraint
every other closed-vocabulary status column already gets. No backfill needed — every existing
row is already `DRAFT`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "ec125daa3d18"
down_revision: str | Sequence[str] | None = "7e2860cacfda"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALID_STATUSES = ("DRAFT", "ACTIVE", "PAUSED", "COMPLETED", "ARCHIVED")


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE campaigns ADD CONSTRAINT valid_campaign_status "
        f"CHECK (status IN {_VALID_STATUSES})"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE campaigns DROP CONSTRAINT valid_campaign_status")
