"""`RecordCrmSyncOutcome` (CLAUDE.md §30, Milestone 20)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.use_cases.record_crm_sync_outcome import RecordCrmSyncOutcome
from colt_domain import CrmSyncRecord, SyncStatus

NOW = datetime.now(UTC)


class FakeCrmSyncRecordRepository:
    def __init__(self) -> None:
        self._by_id: dict[UUID, CrmSyncRecord] = {}
        self.added: list[CrmSyncRecord] = []

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
        record = CrmSyncRecord(
            id=uuid4(),
            organization_id=uuid4(),
            entity_type=entity_type,
            entity_id=entity_id,
            provider_name=provider_name,
            provider_account_id=provider_account_id,
            provider_object_id=provider_object_id,
            sync_status=sync_status,
            created_at=NOW,
            updated_at=NOW,
        )
        self._by_id[record.id] = record
        self.added.append(record)
        return record

    async def get(self, sync_record_id: UUID) -> CrmSyncRecord | None:
        return self._by_id.get(sync_record_id)

    async def get_by_target(
        self, entity_type: str, entity_id: UUID, provider_name: str
    ) -> CrmSyncRecord | None:
        for record in self._by_id.values():
            if (
                record.entity_type == entity_type
                and record.entity_id == entity_id
                and record.provider_name == provider_name
            ):
                return record
        return None

    async def mark_synced(
        self, sync_record_id: UUID, *, provider_object_id: str, at: datetime
    ) -> CrmSyncRecord:
        record = self._by_id[sync_record_id].synced(provider_object_id=provider_object_id, at=at)
        self._by_id[sync_record_id] = record
        return record

    async def mark_failed(self, sync_record_id: UUID, *, error: str, at: datetime) -> CrmSyncRecord:
        record = self._by_id[sync_record_id].failed(error=error, at=at)
        self._by_id[sync_record_id] = record
        return record


async def test_a_first_successful_sync_creates_and_marks_synced() -> None:
    repo = FakeCrmSyncRecordRepository()
    record_outcome = RecordCrmSyncOutcome(repo)
    entity_id = uuid4()

    record = await record_outcome(
        entity_type="Company",
        entity_id=entity_id,
        provider_name="fake",
        provider_account_id="acct-1",
        provider_object_id="fake-company-1",
        error=None,
        now=NOW,
    )

    assert record.sync_status == SyncStatus.SYNCED
    assert record.provider_object_id == "fake-company-1"
    assert len(repo.added) == 1


async def test_a_failed_sync_creates_and_marks_failed() -> None:
    repo = FakeCrmSyncRecordRepository()
    record_outcome = RecordCrmSyncOutcome(repo)
    entity_id = uuid4()

    record = await record_outcome(
        entity_type="Company",
        entity_id=entity_id,
        provider_name="fake",
        provider_account_id="acct-1",
        provider_object_id=None,
        error="simulated 500",
        now=NOW,
    )

    assert record.sync_status == SyncStatus.FAILED
    assert record.last_error == "simulated 500"
    assert len(repo.added) == 1


async def test_a_retry_after_failure_updates_the_same_row_not_a_new_one() -> None:
    repo = FakeCrmSyncRecordRepository()
    record_outcome = RecordCrmSyncOutcome(repo)
    entity_id = uuid4()

    await record_outcome(
        entity_type="Company",
        entity_id=entity_id,
        provider_name="fake",
        provider_account_id="acct-1",
        provider_object_id=None,
        error="simulated 500",
        now=NOW,
    )
    record = await record_outcome(
        entity_type="Company",
        entity_id=entity_id,
        provider_name="fake",
        provider_account_id="acct-1",
        provider_object_id="fake-company-1",
        error=None,
        now=NOW,
    )

    assert record.sync_status == SyncStatus.SYNCED
    assert record.last_error is None
    assert len(repo.added) == 1  # the retry upserted the existing row, no duplicate


async def test_neither_provider_object_id_nor_error_raises() -> None:
    repo = FakeCrmSyncRecordRepository()
    record_outcome = RecordCrmSyncOutcome(repo)

    with pytest.raises(ValueError, match="Exactly one"):
        await record_outcome(
            entity_type="Company",
            entity_id=uuid4(),
            provider_name="fake",
            provider_account_id="acct-1",
            provider_object_id=None,
            error=None,
            now=NOW,
        )


async def test_both_provider_object_id_and_error_raises() -> None:
    repo = FakeCrmSyncRecordRepository()
    record_outcome = RecordCrmSyncOutcome(repo)

    with pytest.raises(ValueError, match="Exactly one"):
        await record_outcome(
            entity_type="Company",
            entity_id=uuid4(),
            provider_name="fake",
            provider_account_id="acct-1",
            provider_object_id="fake-company-1",
            error="simulated 500",
            now=NOW,
        )
