"""`AssignOpportunityOwner` (CLAUDE.md §10.14, Milestone 21) — sets `Opportunity.owner_id` to a
real `User` in the caller's own organization, never an unchecked id. `UserRepository` is already
tenant-scoped (bound to one `organization_id` at construction, the same as every other
repository this package depends on), so a `user_id` belonging to a different organization
resolves to `None` here exactly like it would for any other cross-tenant lookup — the same
"doesn't exist, or exists in a different org" ambiguity `NotFoundError`'s own docstring already
documents as deliberate.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.errors import NotFoundError
from colt_application.ports.opportunity_repository import OpportunityRepository
from colt_application.ports.user_repository import UserRepository
from colt_domain import Opportunity


class AssignOpportunityOwner:
    def __init__(self, opportunities: OpportunityRepository, users: UserRepository) -> None:
        self._opportunities = opportunities
        self._users = users

    async def __call__(self, opportunity_id: UUID, owner_id: UUID, *, now: datetime) -> Opportunity:
        opportunity = await self._opportunities.get(opportunity_id)
        if opportunity is None:
            raise NotFoundError(f"No opportunity found with id {opportunity_id}.")

        owner = await self._users.get(owner_id)
        if owner is None:
            raise NotFoundError(f"No user found with id {owner_id} in this organization.")

        return await self._opportunities.assign_owner(opportunity_id, owner_id, at=now)
