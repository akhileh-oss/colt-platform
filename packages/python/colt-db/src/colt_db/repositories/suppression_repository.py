"""Tenant-scoped repository for `SuppressionEntry` (CLAUDE.md §10.18, §18.1).

`is_suppressed()` deliberately does not go through `TenantScopedRepository._select_scoped()`:
that helper filters strictly on `organization_id == self.organization_id`, which would exclude
every system-wide row (`organization_id IS NULL`) — exactly the rows §10.18 says exist "for
system-wide policy" and §18.1 says "no campaign or agent may override." A suppression check
must see both this organization's own entries and every global one.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select

from colt_db.mappers import suppression_entry_to_domain
from colt_db.models.suppression_entry import SuppressionEntryModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import SuppressionEntry, SuppressionReason


class SqlAlchemySuppressionRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        identifier_type: str,
        identifier: str,
        reason: SuppressionReason,
        source: str,
        organization_scoped: bool = True,
    ) -> SuppressionEntry:
        """`organization_scoped=False` creates a system-wide entry (`organization_id` left
        NULL) — a deliberately rare, explicit choice, never the default, since §18.1 makes a
        global suppression binding on every tenant forever."""
        model = SuppressionEntryModel(
            organization_id=self.organization_id if organization_scoped else None,
            identifier_type=identifier_type,
            identifier=identifier,
            reason=reason.value,
            source=source,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return suppression_entry_to_domain(model)

    async def is_suppressed(self, identifier_type: str, identifier: str) -> bool:
        stmt = select(SuppressionEntryModel.id).where(
            SuppressionEntryModel.identifier_type == identifier_type,
            SuppressionEntryModel.identifier == identifier,
            or_(
                SuppressionEntryModel.organization_id == self.organization_id,
                SuppressionEntryModel.organization_id.is_(None),
            ),
        )
        result = (await self._session.execute(stmt)).first()
        return result is not None

    async def get(self, suppression_entry_id: UUID) -> SuppressionEntry | None:
        stmt = select(SuppressionEntryModel).where(
            SuppressionEntryModel.id == suppression_entry_id,
            or_(
                SuppressionEntryModel.organization_id == self.organization_id,
                SuppressionEntryModel.organization_id.is_(None),
            ),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return suppression_entry_to_domain(model) if model is not None else None
