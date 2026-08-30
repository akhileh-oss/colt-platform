"""Tenant-scoped repository for `AuditLog` (CLAUDE.md §48).

Append-only: this repository deliberately has no update or delete method.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from colt_db.mappers import audit_log_to_domain
from colt_db.models.audit_log import AuditLogModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import AuditLog


class SqlAlchemyAuditLogRepository(TenantScopedRepository):
    async def record(
        self,
        *,
        actor_type: str,
        action: str,
        actor_id: UUID | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> AuditLog:
        model = AuditLogModel(
            organization_id=self.organization_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            audit_metadata=metadata or {},
            request_id=request_id,
            trace_id=trace_id,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return audit_log_to_domain(model)

    async def get(self, audit_log_id: UUID) -> AuditLog | None:
        stmt = self._select_scoped(AuditLogModel).where(AuditLogModel.id == audit_log_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return audit_log_to_domain(model) if model is not None else None
