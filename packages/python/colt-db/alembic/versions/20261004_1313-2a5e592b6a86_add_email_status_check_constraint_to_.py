"""add email_status check constraint to people

Revision ID: 2a5e592b6a86
Revises: 69387639fcf7
Create Date: 2026-10-04 13:13:37.114083

Milestone 05 left `people.email_status` an open, nullable string because nothing yet computed
anything beyond `None`. Milestone 11's `EnrichmentAgent` is the first thing that actually sets
it, assigning one of CLAUDE.md §16.1's `verify_email`-shaped closed values, so this retrofits
the same `CHECK` constraint every other closed-vocabulary status column already gets. `NULL`
stays valid (a person nobody has run `verify_email` on yet) — no backfill needed.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "2a5e592b6a86"
down_revision: str | Sequence[str] | None = "69387639fcf7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALID_STATUSES = ("UNVERIFIED", "VALID", "INVALID", "RISKY", "UNKNOWN")


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE people ADD CONSTRAINT ck_people_valid_email_status "
        f"CHECK (email_status IS NULL OR email_status IN {_VALID_STATUSES})"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE people DROP CONSTRAINT ck_people_valid_email_status")
