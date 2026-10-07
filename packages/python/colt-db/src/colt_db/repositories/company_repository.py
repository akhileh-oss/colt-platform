"""Tenant-scoped repository for `Company` (CLAUDE.md §10.3)."""

from __future__ import annotations

from typing import Any, cast
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

    async def find_by_normalized_domain(self, normalized_domain: str) -> Company | None:
        stmt = self._select_scoped(CompanyModel).where(
            CompanyModel.normalized_domain == normalized_domain
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return company_to_domain(model) if model is not None else None

    async def find_by_linkedin_url(self, linkedin_url: str) -> Company | None:
        stmt = self._select_scoped(CompanyModel).where(CompanyModel.linkedin_url == linkedin_url)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return company_to_domain(model) if model is not None else None

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Company | None:
        """Identity resolution's top-priority layer (`CLAUDE.md` §22: "exact provider ID where
        trustworthy") — matches on the `provider`/`provider_id` keys `source_metadata` stores
        for a record discovered through an `EnrichmentProvider`."""
        stmt = self._select_scoped(CompanyModel).where(
            CompanyModel.source_metadata["provider"].astext == provider,
            CompanyModel.source_metadata["provider_id"].astext == provider_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return company_to_domain(model) if model is not None else None

    async def list_all(self) -> list[Company]:
        """Every company in this organization — the ICP-performance analytics read model
        (Milestone 22) groups over this, since there is no stored "ICP segment" to filter by."""
        stmt = self._select_scoped(CompanyModel)
        models = (await self._session.execute(stmt)).scalars().all()
        return [company_to_domain(model) for model in models]

    async def update(self, company_id: UUID, **fields: Any) -> Company:
        """Set only the given fields; a field omitted (or passed `None`) is left unchanged —
        `EnrichCompany` (Milestone 11) only ever passes fields a provider actually returned, so
        this never needs to clear a field back to `None`."""
        stmt = self._select_scoped(CompanyModel).where(CompanyModel.id == company_id)
        model = cast(CompanyModel, (await self._session.execute(stmt)).scalar_one())
        for key, value in fields.items():
            if value is not None:
                setattr(model, key, value)
        await self._session.flush()
        await self._session.refresh(model)
        return company_to_domain(model)
