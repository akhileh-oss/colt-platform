"""Tenant-scoped repository for `Opportunity` (CLAUDE.md §10.14, §11.3, Milestone 21)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_db.mappers import opportunity_to_domain
from colt_db.models.opportunity import OpportunityModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Opportunity, PipelineStage

#: Pipeline stages a company's opportunity is still "open" in — neither closed-won nor
#: closed-lost. The dedup check (`get_open_by_company`) treats anything outside this set as
#: eligible for a brand new opportunity rather than reusing a closed one.
_OPEN_STAGES = frozenset(PipelineStage) - {PipelineStage.WON, PipelineStage.LOST}


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
        is_estimated_value: bool = False,
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
            is_estimated_value=is_estimated_value,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return opportunity_to_domain(model)

    async def get(self, opportunity_id: UUID) -> Opportunity | None:
        stmt = self._select_scoped(OpportunityModel).where(OpportunityModel.id == opportunity_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return opportunity_to_domain(model) if model is not None else None

    async def get_open_by_company(self, company_id: UUID) -> Opportunity | None:
        """The duplicate-creation check: is there already an open (non-`WON`/`LOST`)
        opportunity for this company? The oldest one, if more than one somehow exists, is
        treated as "the" opportunity — a deterministic, stable choice rather than an arbitrary
        database-ordering one."""
        stmt = (
            self._select_scoped(OpportunityModel)
            .where(
                OpportunityModel.company_id == company_id,
                OpportunityModel.pipeline_stage.in_([s.value for s in _OPEN_STAGES]),
            )
            .order_by(OpportunityModel.created_at)
        )
        model = (await self._session.execute(stmt)).scalars().first()
        return opportunity_to_domain(model) if model is not None else None

    async def list_all(self) -> list[Opportunity]:
        stmt = self._select_scoped(OpportunityModel).order_by(OpportunityModel.created_at)
        models = (await self._session.execute(stmt)).scalars().all()
        return [opportunity_to_domain(model) for model in models]

    async def update_stage(
        self, opportunity_id: UUID, stage: PipelineStage, *, at: datetime
    ) -> Opportunity:
        stmt = self._select_scoped(OpportunityModel).where(OpportunityModel.id == opportunity_id)
        model = (await self._session.execute(stmt)).scalar_one()
        model.pipeline_stage = stage.value
        model.updated_at = at
        await self._session.flush()
        await self._session.refresh(model)
        return opportunity_to_domain(model)

    async def assign_owner(
        self, opportunity_id: UUID, owner_id: UUID, *, at: datetime
    ) -> Opportunity:
        stmt = self._select_scoped(OpportunityModel).where(OpportunityModel.id == opportunity_id)
        model = (await self._session.execute(stmt)).scalar_one()
        model.owner_id = owner_id
        model.updated_at = at
        await self._session.flush()
        await self._session.refresh(model)
        return opportunity_to_domain(model)

    async def update_value(
        self,
        opportunity_id: UUID,
        *,
        estimated_value: float,
        currency: str,
        is_estimate: bool,
        at: datetime,
    ) -> Opportunity:
        stmt = self._select_scoped(OpportunityModel).where(OpportunityModel.id == opportunity_id)
        model = (await self._session.execute(stmt)).scalar_one()
        model.estimated_value = estimated_value
        model.currency = currency
        model.is_estimated_value = is_estimate
        model.updated_at = at
        await self._session.flush()
        await self._session.refresh(model)
        return opportunity_to_domain(model)
