"""add verification_status check constraint to evidence

Revision ID: 69387639fcf7
Revises: 425cb37e5cee
Create Date: 2026-10-04 10:26:27.743299

Milestone 05 left `evidence.verification_status` an open string because nothing yet computed
anything beyond the `UNVERIFIED` default. Milestone 10 adds real source-verification logic
(`colt_application.use_cases.record_evidence`) that assigns one of CLAUDE.md §20's five closed
values, so this retrofits the same `CHECK` constraint every other closed-vocabulary status
column already gets. No backfill needed — every existing row is already `UNVERIFIED`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "69387639fcf7"
down_revision: str | Sequence[str] | None = "425cb37e5cee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALID_STATUSES = ("UNVERIFIED", "VERIFIED", "STALE", "DISPUTED", "REJECTED")


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE evidence ADD CONSTRAINT ck_evidence_valid_verification_status "
        f"CHECK (verification_status IN {_VALID_STATUSES})"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE evidence DROP CONSTRAINT ck_evidence_valid_verification_status")
