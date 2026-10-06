"""The Opportunity repository port (CLAUDE.md §2.3, §10.14).

Milestone 20 is the first caller that needs to read an `Opportunity` from the application layer
(CRM sync reads whatever entity it is told to sync) — no prior milestone's Build list named this
port.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from colt_domain import Opportunity, PipelineStage


class OpportunityRepository(Protocol):
    async def add(
        self,
        *,
        company_id: UUID,
        primary_person_id: UUID | None = None,
        lead_id: UUID | None = None,
        pipeline_stage: PipelineStage = PipelineStage.QUALIFIED,
        estimated_value: float | None = None,
        currency: str | None = None,
        probability: float | None = None,
        owner_id: UUID | None = None,
        source: str | None = None,
    ) -> Opportunity: ...

    async def get(self, opportunity_id: UUID) -> Opportunity | None: ...
