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
from sqlalchemy.exc import IntegrityError

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
        global suppression binding on every tenant forever.

        Idempotent under concurrency (CLAUDE.md §27, §96, Milestone 27's "duplicate webhook
        simulations"): two deliveries of the same unsubscribe webhook racing each other both
        pass `is_suppressed()`'s own check before either commits — `uq_suppression_entries_org_
        identifier` is what actually serializes them. The loser does not raise; "ensure this
        identifier is suppressed" already holds once the winner's row exists, so this returns
        that row rather than making the caller handle a conflict a plain unsubscribe retry has
        no business ever seeing (the unsubscribe router's own docstring already promises
        exactly this: "never let a mail client's one-click retry start erroring once the first
        attempt has already succeeded").
        """
        model = SuppressionEntryModel(
            organization_id=self.organization_id if organization_scoped else None,
            identifier_type=identifier_type,
            identifier=identifier,
            reason=reason.value,
            source=source,
        )
        try:
            # A SAVEPOINT (`begin_nested`), not a plain `flush()`: on conflict, only this
            # savepoint rolls back, leaving the caller's own outer transaction (and session)
            # still usable for the `find_by_identifier` re-query below. Rolling back the whole
            # session here (the first fix attempted) left it in "Can't operate on closed
            # transaction inside context manager" for the rest of the caller's own `async with
            # session.begin():` block — a real failure mode, caught by running this fix against
            # real concurrent deliveries, not merely reasoned about.
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as exc:
            if "uq_suppression_entries_org_identifier" not in str(exc.orig):
                raise
            existing = await self.find_by_identifier(identifier_type, identifier)
            if existing is None:
                # flush() raised this exact unique-constraint violation, so a matching row
                # must exist — reaching here would mean the database and this query disagree.
                raise RuntimeError(
                    "uq_suppression_entries_org_identifier violated but no matching row found"
                ) from exc
            return existing
        await self._session.refresh(model)
        return suppression_entry_to_domain(model)

    async def find_by_identifier(
        self, identifier_type: str, identifier: str
    ) -> SuppressionEntry | None:
        stmt = select(SuppressionEntryModel).where(
            SuppressionEntryModel.identifier_type == identifier_type,
            SuppressionEntryModel.identifier == identifier,
            or_(
                SuppressionEntryModel.organization_id == self.organization_id,
                SuppressionEntryModel.organization_id.is_(None),
            ),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return suppression_entry_to_domain(model) if model is not None else None

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
