"""The CrmSyncRecord repository port (CLAUDE.md §2.3, §30)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from colt_domain import CrmSyncRecord, SyncStatus


class CrmSyncRecordRepository(Protocol):
    async def add(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        provider_name: str,
        provider_account_id: str,
        provider_object_id: str | None = None,
        sync_status: SyncStatus = SyncStatus.PENDING,
    ) -> CrmSyncRecord: ...

    async def get(self, sync_record_id: UUID) -> CrmSyncRecord | None: ...

    async def get_by_target(
        self, entity_type: str, entity_id: UUID, provider_name: str
    ) -> CrmSyncRecord | None: ...

    async def mark_synced(
        self, sync_record_id: UUID, *, provider_object_id: str, at: datetime
    ) -> CrmSyncRecord: ...

    async def mark_failed(
        self, sync_record_id: UUID, *, error: str, at: datetime
    ) -> CrmSyncRecord: ...
