"""Tenant-scoped repository for `Person` (CLAUDE.md §10.4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from colt_db.mappers import person_to_domain
from colt_db.models.person import PersonModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Person


class SqlAlchemyPersonRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        company_id: UUID,
        full_name: str,
        first_name: str | None = None,
        last_name: str | None = None,
        title: str | None = None,
        seniority: str | None = None,
        department: str | None = None,
        email: str | None = None,
        email_status: str | None = None,
        linkedin_url: str | None = None,
        location: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> Person:
        model = PersonModel(
            organization_id=self.organization_id,
            company_id=company_id,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            title=title,
            seniority=seniority,
            department=department,
            email=email,
            email_status=email_status,
            linkedin_url=linkedin_url,
            location=location,
            source_metadata=source_metadata or {},
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return person_to_domain(model)

    async def get(self, person_id: UUID) -> Person | None:
        stmt = self._select_scoped(PersonModel).where(PersonModel.id == person_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return person_to_domain(model) if model is not None else None
