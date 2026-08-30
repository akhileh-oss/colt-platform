"""Tenant-scoped repository for `Lead` (CLAUDE.md §10.7)."""

from __future__ import annotations

from uuid import UUID

from colt_db.mappers import lead_to_domain
from colt_db.models.lead import LeadModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Lead, LeadStatus


class SqlAlchemyLeadRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        company_id: UUID,
        person_id: UUID,
        status: LeadStatus = LeadStatus.NEW,
        source: str | None = None,
        current_stage: str | None = None,
        priority: str | None = None,
    ) -> Lead:
        model = LeadModel(
            organization_id=self.organization_id,
            company_id=company_id,
            person_id=person_id,
            status=status.value,
            source=source,
            current_stage=current_stage,
            priority=priority,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return lead_to_domain(model)

    async def get(self, lead_id: UUID) -> Lead | None:
        stmt = self._select_scoped(LeadModel).where(LeadModel.id == lead_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return lead_to_domain(model) if model is not None else None
