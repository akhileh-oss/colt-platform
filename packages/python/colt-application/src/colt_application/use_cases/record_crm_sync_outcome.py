"""`RecordCrmSyncOutcome` (CLAUDE.md §30, Milestone 20) — the one write that turns a CRM
provider call's result into a `CrmSyncRecord`, mirroring `RecordReplyClassification`'s role for
`ReplyIntelligenceAgent`: pure persistence logic, no I/O against the CRM provider itself (that
belongs to the Temporal activity, the composition root that owns the actual provider call).

Upserts by `(entity_type, entity_id, provider_name)` — the first sync of an entity creates the
tracking row, every later attempt (a reconciliation re-run, a retry after failure) updates the
same one, never creating a duplicate mapping to the same external object.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.ports.crm_sync_record_repository import CrmSyncRecordRepository
from colt_domain import CrmSyncRecord


class RecordCrmSyncOutcome:
    def __init__(self, crm_sync_records: CrmSyncRecordRepository) -> None:
        self._crm_sync_records = crm_sync_records

    async def __call__(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        provider_name: str,
        provider_account_id: str,
        provider_object_id: str | None,
        error: str | None,
        now: datetime,
    ) -> CrmSyncRecord:
        if (provider_object_id is None) == (error is None):
            raise ValueError(
                "Exactly one of provider_object_id (success) or error (failure) must be given."
            )

        record = await self._crm_sync_records.get_by_target(entity_type, entity_id, provider_name)
        if record is None:
            record = await self._crm_sync_records.add(
                entity_type=entity_type,
                entity_id=entity_id,
                provider_name=provider_name,
                provider_account_id=provider_account_id,
            )

        if provider_object_id is not None:
            return await self._crm_sync_records.mark_synced(
                record.id, provider_object_id=provider_object_id, at=now
            )

        if error is None:
            raise ValueError(
                "Exactly one of provider_object_id (success) or error (failure) must be given."
            )
        return await self._crm_sync_records.mark_failed(record.id, error=error, at=now)
