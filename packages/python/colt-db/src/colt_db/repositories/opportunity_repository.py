"""Tenant-scoped repository for `Opportunity` (CLAUDE.md §10.14)."""

from __future__ import annotations

from uuid import UUID

from colt_db.mappers import opportunity_to_domain
from colt_db.models.opportunity import OpportunityModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Opportunity, PipelineStage


class SqlAlchemyOpportunityRepository(TenantScopedRepository):
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
    ) -> Opportunity:
        model = OpportunityModel(
            organization_id=self.organization_id,
            company_id=company_id,
            primary_person_id=primary_person_id,
            lead_id=lead_id,
            pipeline_stage=pipeline_stage.value,
            estimated_value=estimated_value,
            currency=currency,
            probability=probability,
            owner_id=owner_id,
            source=source,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return opportunity_to_domain(model)

    async def get(self, opportunity_id: UUID) -> Opportunity | None:
        stmt = self._select_scoped(OpportunityModel).where(OpportunityModel.id == opportunity_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return opportunity_to_domain(model) if model is not None else None
