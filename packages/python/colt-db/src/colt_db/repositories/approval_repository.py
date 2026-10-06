"""Tenant-scoped repository for `Approval` (CLAUDE.md §10.17)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_db.mappers import approval_to_domain
from colt_db.models.approval import ApprovalModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Approval, ApprovalStatus


class SqlAlchemyApprovalRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        action_type: str,
        requested_by: UUID | None = None,
    ) -> Approval:
        model = ApprovalModel(
            organization_id=self.organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action_type=action_type,
            requested_by=requested_by,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return approval_to_domain(model)

    async def get(self, approval_id: UUID) -> Approval | None:
        stmt = self._select_scoped(ApprovalModel).where(ApprovalModel.id == approval_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return approval_to_domain(model) if model is not None else None

    async def get_latest_for_entity(self, entity_type: str, entity_id: UUID) -> Approval | None:
        """The most recently requested approval for an entity — the one a decision applies to."""
        stmt = (
            self._select_scoped(ApprovalModel)
            .where(ApprovalModel.entity_type == entity_type, ApprovalModel.entity_id == entity_id)
            .order_by(ApprovalModel.created_at.desc())
            .limit(1)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return approval_to_domain(model) if model is not None else None

    async def decide(
        self,
        approval_id: UUID,
        *,
        status: ApprovalStatus,
        approved_by: UUID,
        reason: str | None,
        decided_at: datetime,
    ) -> Approval:
        """Record a human decision. `status` must be `APPROVED` or `REJECTED` — the caller's
        job, not this repository's, since deciding which transitions are valid is application
        logic (§5.2), not infrastructure."""
        stmt = self._select_scoped(ApprovalModel).where(ApprovalModel.id == approval_id)
        model = (await self._session.execute(stmt)).scalar_one()
        model.status = status.value
        model.approved_by = approved_by
        model.reason = reason
        model.decided_at = decided_at
        await self._session.flush()
        await self._session.refresh(model)
        return approval_to_domain(model)
