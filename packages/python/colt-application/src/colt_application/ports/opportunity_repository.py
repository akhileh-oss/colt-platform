"""The Opportunity repository port (CLAUDE.md §2.3, §10.14, §11.3, Milestone 21).

Milestone 20 was the first caller that needed to read an `Opportunity` from the application
layer (CRM sync reads whatever entity it is told to sync); Milestone 21's state machine, owner
assignment and dedup check are this port's first callers that need to write one.
"""

from __future__ import annotations

from datetime import datetime
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
        is_estimated_value: bool = False,
    ) -> Opportunity: ...

    async def get(self, opportunity_id: UUID) -> Opportunity | None: ...

    async def get_open_by_company(self, company_id: UUID) -> Opportunity | None: ...

    async def list_all(self) -> list[Opportunity]: ...

    async def update_stage(
        self, opportunity_id: UUID, stage: PipelineStage, *, at: datetime
    ) -> Opportunity: ...

    async def assign_owner(
        self, opportunity_id: UUID, owner_id: UUID, *, at: datetime
    ) -> Opportunity: ...

    async def update_value(
        self,
        opportunity_id: UUID,
        *,
        estimated_value: float,
        currency: str,
        is_estimate: bool,
        at: datetime,
    ) -> Opportunity: ...
