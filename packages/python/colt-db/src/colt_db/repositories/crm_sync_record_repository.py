"""Tenant-scoped repository for `CrmSyncRecord` (CLAUDE.md §30)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_db.mappers import crm_sync_record_to_domain
from colt_db.models.crm_sync_record import CrmSyncRecordModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import CrmSyncRecord, SyncStatus


class SqlAlchemyCrmSyncRecordRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        provider_name: str,
        provider_account_id: str,
        provider_object_id: str | None = None,
        sync_status: SyncStatus = SyncStatus.PENDING,
    ) -> CrmSyncRecord:
        model = CrmSyncRecordModel(
            organization_id=self.organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            provider_name=provider_name,
            provider_account_id=provider_account_id,
            provider_object_id=provider_object_id,
            sync_status=sync_status.value,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return crm_sync_record_to_domain(model)

    async def get(self, sync_record_id: UUID) -> CrmSyncRecord | None:
        stmt = self._select_scoped(CrmSyncRecordModel).where(
            CrmSyncRecordModel.id == sync_record_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return crm_sync_record_to_domain(model) if model is not None else None

    async def get_by_target(
        self, entity_type: str, entity_id: UUID, provider_name: str
    ) -> CrmSyncRecord | None:
        """The upsert lookup every sync attempt starts with — at most one row per
        (entity, provider), enforced by the `uq_crm_sync_target` constraint."""
        stmt = self._select_scoped(CrmSyncRecordModel).where(
            CrmSyncRecordModel.entity_type == entity_type,
            CrmSyncRecordModel.entity_id == entity_id,
            CrmSyncRecordModel.provider_name == provider_name,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return crm_sync_record_to_domain(model) if model is not None else None

    async def mark_synced(
        self, sync_record_id: UUID, *, provider_object_id: str, at: datetime
    ) -> CrmSyncRecord:
        stmt = self._select_scoped(CrmSyncRecordModel).where(
            CrmSyncRecordModel.id == sync_record_id
        )
        model = (await self._session.execute(stmt)).scalar_one()
        model.provider_object_id = provider_object_id
        model.sync_status = SyncStatus.SYNCED.value
        model.last_synced_at = at
        model.last_error = None
        model.updated_at = at
        await self._session.flush()
        await self._session.refresh(model)
        return crm_sync_record_to_domain(model)

    async def mark_failed(self, sync_record_id: UUID, *, error: str, at: datetime) -> CrmSyncRecord:
        stmt = self._select_scoped(CrmSyncRecordModel).where(
            CrmSyncRecordModel.id == sync_record_id
        )
        model = (await self._session.execute(stmt)).scalar_one()
        model.sync_status = SyncStatus.FAILED.value
        model.last_error = error
        model.updated_at = at
        await self._session.flush()
        await self._session.refresh(model)
        return crm_sync_record_to_domain(model)
