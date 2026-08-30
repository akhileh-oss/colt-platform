"""SQLAlchemy implementation of `OrganizationRepository`.

Not tenant-scoped: Organization is the tenancy root (see `colt_db.tenancy` module docstring).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from colt_db.mappers import organization_to_domain
from colt_db.models.organization import OrganizationModel
from colt_domain import Organization


class SqlAlchemyOrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID) -> Organization | None:
        model = await self._session.get(OrganizationModel, organization_id)
        return organization_to_domain(model) if model is not None else None

    async def get_by_slug(self, slug: str) -> Organization | None:
        stmt = select(OrganizationModel).where(OrganizationModel.slug == slug)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return organization_to_domain(model) if model is not None else None
