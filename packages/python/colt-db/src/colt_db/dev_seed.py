"""Local development seed data: two organizations, each with one Keycloak-linked user.

Matches the two test identities in `infrastructure/docker/keycloak/colt-realm.json` — Alice
(Acme Corp) and Bob (Globex Inc) — so a real token fetched from local Keycloak resolves to a
real organization end to end.

Used by `apps/api/scripts/seed_dev_data.py` (the CLI entry point, `make seed`) and by
`tests/integration/test_auth_end_to_end.py` (which cannot rely on the CLI having been run out
of band, since the tenant-isolation tests in the same directory truncate these tables between
tests). Both call this directly rather than the test shelling out to the script, or the script
duplicating this data — one definition, two callers.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Fixed to match the `id` fields in the Keycloak realm import — deterministic, no cross-system
# lookup needed.
ALICE_SUBJECT = "11111111-1111-4111-8111-111111111111"
BOB_SUBJECT = "22222222-2222-4222-8222-222222222222"

ORGANIZATIONS = [
    {"slug": "acme-corp", "name": "Acme Corp"},
    {"slug": "globex-inc", "name": "Globex Inc"},
]

USERS = [
    {
        "organization_slug": "acme-corp",
        "external_auth_id": ALICE_SUBJECT,
        "email": "alice@acme-corp.example",
        "name": "Alice Owner",
        "role": "OWNER",
    },
    {
        "organization_slug": "globex-inc",
        "external_auth_id": BOB_SUBJECT,
        "email": "bob@globex-inc.example",
        "name": "Bob Owner",
        "role": "OWNER",
    },
]


async def seed_dev_organizations_and_users(session: AsyncSession) -> None:
    """Insert (or update, if already present) the fixed dev organizations and users.

    Idempotent: safe to call more than once, and safe to call after the tables were just
    truncated. Uses the RLS bypass flag — this is dev/test-only seed data, not a request path.
    """
    await session.execute(text("SET LOCAL app.bypass_rls = 'true'"))

    slug_to_id: dict[str, UUID] = {}
    for org in ORGANIZATIONS:
        row = await session.execute(
            text(
                "INSERT INTO organizations (name, slug) VALUES (:name, :slug) "
                "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name "
                "RETURNING id"
            ),
            org,
        )
        slug_to_id[org["slug"]] = row.scalar_one()

    for user in USERS:
        await session.execute(
            text(
                "INSERT INTO users (organization_id, external_auth_id, email, name, role) "
                "VALUES (:org_id, :external_auth_id, :email, :name, :role) "
                "ON CONFLICT (external_auth_id) DO UPDATE SET "
                "organization_id = EXCLUDED.organization_id, email = EXCLUDED.email, "
                "name = EXCLUDED.name, role = EXCLUDED.role"
            ),
            {**user, "org_id": slug_to_id[user["organization_slug"]]},
        )
