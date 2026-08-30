"""CLI entry point for `make seed`. The actual seed data lives in `colt_db.dev_seed`, shared
with `tests/integration/test_auth_end_to_end.py` — see that module's docstring for why.

    uv run python apps/api/scripts/seed_dev_data.py
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from colt_config import get_settings
from colt_db.dev_seed import seed_dev_organizations_and_users
from colt_db.session import create_engine


async def main() -> int:
    settings = get_settings()
    if not settings.is_local:
        print(
            f"Refusing to seed dev data outside a local environment (APP_ENV={settings.app.env}).",
            file=sys.stderr,
        )
        return 1

    engine = create_engine(settings.database)
    try:
        async with engine.begin() as conn:
            session = AsyncSession(bind=conn, expire_on_commit=False)
            await seed_dev_organizations_and_users(session)
    finally:
        await engine.dispose()

    print("Seeded 2 organizations and 2 users (alice@acme-corp, bob@globex-inc).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
