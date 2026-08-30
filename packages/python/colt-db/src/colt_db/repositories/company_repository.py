"""Tenant-scoped repository for `Company` (CLAUDE.md §10.3)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from colt_db.mappers import company_to_domain
from colt_db.models.company import CompanyModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Company


class SqlAlchemyCompanyRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        name: str,
        domain: str | None = None,
        normalized_domain: str | None = None,
        industry: str | None = None,
        employee_count: int | None = None,
        revenue_range: str | None = None,
        country: str | None = None,
        region: str | None = None,
        city: str | None = None,
        description: str | None = None,
        website_url: str | None = None,
        linkedin_url: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> Company:
        model = CompanyModel(
            organization_id=self.organization_id,
            name=name,
            domain=domain,
            normalized_domain=normalized_domain,
            industry=industry,
            employee_count=employee_count,
            revenue_range=revenue_range,
            country=country,
            region=region,
            city=city,
            description=description,
            website_url=website_url,
            linkedin_url=linkedin_url,
            source_metadata=source_metadata or {},
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return company_to_domain(model)

    async def get(self, company_id: UUID) -> Company | None:
        stmt = self._select_scoped(CompanyModel).where(CompanyModel.id == company_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return company_to_domain(model) if model is not None else None
