"""The activity that gives Milestone 07's trace proof a real database span.

Exists solely so `TraceCheckWorkflow` has something at the end of the chain that actually
touches PostgreSQL — proving CLAUDE.md §68's acceptance criterion (a trace spanning
API → workflow → activity → DB) with a real query, not a stand-in.
"""

from __future__ import annotations

from sqlalchemy import text
from temporalio import activity

from colt_db import get_default_engine
from colt_observability import get_logger

logger = get_logger(__name__)


@activity.defn
async def count_organizations() -> int:
    """Run one real, tenant-agnostic count query and return it.

    Deliberately queries directly rather than going through
    `SqlAlchemyOrganizationRepository`'s tenant-scoping machinery: this is diagnostic
    infrastructure proving the trace pipeline, not a product operation with an organization to
    scope to.
    """
    engine = get_default_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM organizations"))
        count: int = result.scalar_one()
    logger.info("counted organizations", extra={"operation": "count_organizations"})
    return count
