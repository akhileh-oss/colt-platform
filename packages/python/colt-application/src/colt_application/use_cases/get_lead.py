"""Look up a lead by id, scoped to the caller's organization (CLAUDE.md §2.3, §10.7).

The use case `colt-agents`' `get_lead` tool calls — a typed tool must never query
`colt-db` directly (§2.3: Typed Tool → Application Service → Repository → PostgreSQL), so this
is the one place that boundary is crossed for lead reads.
"""

from __future__ import annotations

from uuid import UUID

from colt_application.errors import NotFoundError
from colt_application.ports.lead_repository import LeadRepository
from colt_domain import Lead


class GetLead:
    """Use case: a lead id, scoped to one organization → that `Lead`, or `NotFoundError`."""

    def __init__(self, leads: LeadRepository) -> None:
        self._leads = leads

    async def __call__(self, lead_id: UUID) -> Lead:
        lead = await self._leads.get(lead_id)
        if lead is None:
            raise NotFoundError(f"No lead {lead_id} in this organization.")
        return lead
