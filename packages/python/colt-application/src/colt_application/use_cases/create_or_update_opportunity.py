"""`CreateOrUpdateOpportunity` (CLAUDE.md §10.14, §11.3, §12.11, Milestone 21) — turns a positive
conversation into an auditable `Opportunity` without ever creating a duplicate.

The dedup rule: at most one *open* (non-`WON`/`LOST`) `Opportunity` per `company_id`. If one
already exists, it is returned unchanged by default — a later reply from the same positive
conversation must not spawn a second pipeline entry for a deal already being tracked. Only when
the caller supplies a value Colt doesn't have yet (the opportunity has none, and this call
offers one) is the existing row updated in place, never duplicated. This is the literal
mechanism behind "positive conversations can become auditable opportunities without duplicate
creation" (Milestone 21's acceptance criterion) — the check that actually prevents the
duplicate, not just a hope that it won't happen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from colt_application.ports.opportunity_repository import OpportunityRepository
from colt_domain import Opportunity


@dataclass(frozen=True, slots=True)
class OpportunityUpsertResult:
    opportunity: Opportunity
    was_created: bool


class CreateOrUpdateOpportunity:
    def __init__(self, opportunities: OpportunityRepository) -> None:
        self._opportunities = opportunities

    async def __call__(
        self,
        *,
        company_id: UUID,
        primary_person_id: UUID | None = None,
        lead_id: UUID | None = None,
        source: str,
        estimated_value: float | None = None,
        currency: str | None = None,
        is_estimate: bool = False,
        now: datetime,
    ) -> OpportunityUpsertResult:
        existing = await self._opportunities.get_open_by_company(company_id)
        if existing is not None:
            if existing.estimated_value is None and estimated_value is not None and currency:
                updated = await self._opportunities.update_value(
                    existing.id,
                    estimated_value=estimated_value,
                    currency=currency,
                    is_estimate=is_estimate,
                    at=now,
                )
                return OpportunityUpsertResult(opportunity=updated, was_created=False)
            return OpportunityUpsertResult(opportunity=existing, was_created=False)

        created = await self._opportunities.add(
            company_id=company_id,
            primary_person_id=primary_person_id,
            lead_id=lead_id,
            source=source,
            estimated_value=estimated_value,
            currency=currency,
            is_estimated_value=is_estimate,
        )
        return OpportunityUpsertResult(opportunity=created, was_created=True)
