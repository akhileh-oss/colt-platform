"""`AddSuppressionEntry` (CLAUDE.md §10.18, §18.1, §18.2, §48, Milestone 16)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.use_cases.add_suppression_entry import AddSuppressionEntry
from colt_domain import AuditLog, SuppressionEntry, SuppressionReason

NOW = datetime.now(UTC)


class FakeSuppressionRepository:
    def __init__(self) -> None:
        self.added: list[SuppressionEntry] = []

    async def add(self, **kwargs: Any) -> SuppressionEntry:
        organization_scoped = kwargs.pop("organization_scoped", True)
        entry = SuppressionEntry(
            id=uuid4(),
            organization_id=uuid4() if organization_scoped else None,
            created_at=NOW,
            updated_at=NOW,
            **kwargs,
        )
        self.added.append(entry)
        return entry

    async def is_suppressed(self, identifier_type: str, identifier: str) -> bool:
        raise NotImplementedError

    async def get(self, suppression_entry_id: UUID) -> SuppressionEntry | None:
        raise NotImplementedError


class FakeAuditLogRepository:
    def __init__(self) -> None:
        self.recorded: list[AuditLog] = []

    async def record(self, **kwargs: Any) -> AuditLog:
        log = AuditLog(id=uuid4(), organization_id=uuid4(), created_at=NOW, **kwargs)
        self.recorded.append(log)
        return log


@pytest.mark.asyncio
async def test_adding_a_suppression_entry_records_it_and_an_audit_event() -> None:
    suppressions = FakeSuppressionRepository()
    audit_logs = FakeAuditLogRepository()
    add_suppression = AddSuppressionEntry(suppressions, audit_logs)

    entry = await add_suppression(
        identifier_type="email",
        identifier="bounced@example.com",
        reason=SuppressionReason.BOUNCE,
        source="email-provider-webhook",
        actor_id=None,
    )

    assert entry.identifier == "bounced@example.com"
    assert entry.reason == SuppressionReason.BOUNCE
    assert entry.organization_id is not None
    (log,) = audit_logs.recorded
    assert log.action == "suppression_added"
    assert log.entity_id == entry.id
    assert log.actor_type == "system"


@pytest.mark.asyncio
async def test_a_system_wide_suppression_entry_has_no_organization() -> None:
    suppressions = FakeSuppressionRepository()
    audit_logs = FakeAuditLogRepository()
    add_suppression = AddSuppressionEntry(suppressions, audit_logs)

    entry = await add_suppression(
        identifier_type="email",
        identifier="blocked@example.com",
        reason=SuppressionReason.LEGAL_REQUEST,
        source="legal-review",
        organization_scoped=False,
        actor_id=uuid4(),
    )

    assert entry.organization_id is None
    (log,) = audit_logs.recorded
    assert log.actor_type == "user"
    assert log.metadata["organization_scoped"] is False
