"""unique indexes preventing duplicate company domain and person email

Revision ID: b606dfdd0d97
Revises: ee0e282d11ae
Create Date: 2026-10-07 18:15:09.059924

Milestone 27's own `tests/soak/test_identity_resolution_concurrency.py` reproduced, for real
against a disposable Postgres database, exactly the race CLAUDE.md §22/§96 warn a soak test
must catch: `DiscoverCompany`/`DiscoverPerson`'s check-then-insert dedup logic is not
concurrency-safe without a real unique constraint behind it — ten concurrent calls for the same
company domain produced ten rows, not one. These two partial unique indexes are the fix;
`colt_db.repositories.{company,person}_repository`'s own `add()` now translates the resulting
`IntegrityError` into `colt_domain.DuplicateIdentityError`.

Partial (not a plain unique column) because both `normalized_domain` and `email` are nullable,
and multiple companies/people with no known domain/email must still coexist.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b606dfdd0d97"
down_revision: str | None = "ee0e282d11ae"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_companies_org_normalized_domain",
        "companies",
        ["organization_id", "normalized_domain"],
        unique=True,
        postgresql_where=sa.text("normalized_domain IS NOT NULL"),
    )
    op.create_index(
        "uq_people_org_email",
        "people",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_people_org_email",
        table_name="people",
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.drop_index(
        "uq_companies_org_normalized_domain",
        table_name="companies",
        postgresql_where=sa.text("normalized_domain IS NOT NULL"),
    )
