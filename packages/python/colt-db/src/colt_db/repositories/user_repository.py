"""SQLAlchemy implementations of the user repository ports (ADR-0005).

`SqlAlchemyUserDirectory` and `SqlAlchemyUserRepository` are separate classes, not two methods
on one, so that the narrow RLS bypass (`app.bypass_rls`) is visible at the call site: nothing
calling into a `UserRepository` can accidentally hit the bypass path, because that class does
not have one.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from colt_db.mappers import user_to_domain
from colt_db.models.user import UserModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import User


class SqlAlchemyUserDirectory:
    """Looks a user up by verified external identity, before an organization is known.

    The one call site in the codebase that sets ``app.bypass_rls`` — see the Alembic migration
    for the policy this satisfies, and ADR-0005 for why the bypass is safe: the query is always
    scoped to one ``external_auth_id``, which only ever reaches this method already verified by
    JWT signature checking (colt-api never calls this with client-supplied input).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_external_auth_id(self, external_auth_id: str) -> User | None:
        await self._session.execute(text("SET LOCAL app.bypass_rls = 'true'"))
        stmt = select(UserModel).where(UserModel.external_auth_id == external_auth_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return user_to_domain(model) if model is not None else None


class SqlAlchemyUserRepository(TenantScopedRepository):
    """Tenant-scoped user access. Construct via ``TenantScopedRepository.create()``."""

    async def get(self, user_id: UUID) -> User | None:
        stmt = self._select_scoped(UserModel).where(UserModel.id == user_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return user_to_domain(model) if model is not None else None

    async def list_active(self) -> list[User]:
        stmt = self._select_scoped(UserModel).where(UserModel.status == "ACTIVE")
        models = (await self._session.execute(stmt)).scalars().all()
        return [user_to_domain(m) for m in models]
