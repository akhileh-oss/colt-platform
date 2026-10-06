"""`FakeCRMProvider` — the test double CLAUDE.md §28.1 requires every adapter to have, and the
only `CRMProvider` adapter this milestone builds (no real CRM vendor named by CLAUDE.md §30, the
same situation `FakeSignalTriggerSource` was in for Milestone 12).

Supports the "failure simulation" CLAUDE.md §93 calls essential for resilience testing: queue a
`ProviderError` against a given `(kind, external_id)` and the next sync call for that target
raises it instead of succeeding. Upserts by `(kind, external_id)` — a retry (after a queued
failure, or a deliberate re-sync) targets the exact same provider object it did last time,
never creating a duplicate, the same idempotency a real CRM adapter must provide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from colt_integrations.crm.port import CrmSyncResult


@dataclass
class _StoredObject:
    provider_object_id: str
    fields: dict[str, Any] = field(default_factory=dict)


class FakeCRMProvider:
    def __init__(self, *, authenticated: bool = True) -> None:
        self._authenticated = authenticated
        self._objects: dict[tuple[str, str], _StoredObject] = {}
        self._pending_failures: dict[tuple[str, str], list[Exception]] = {}
        self._next_id = 1

    def queue_failure(self, kind: str, external_id: str, error: Exception) -> None:
        """The next sync call for this `(kind, external_id)` raises `error` instead of
        succeeding — once. Queue several to simulate N transient failures before recovery."""
        self._pending_failures.setdefault((kind, external_id), []).append(error)

    def reset(self) -> None:
        """Clear every stored object and queued failure. For test isolation only — a composition
        root that keeps one long-lived instance for a process's whole lifetime (as
        `colt_workflows.activities.crm_sync` does) never calls this itself."""
        self._objects.clear()
        self._pending_failures.clear()
        self._next_id = 1

    def stored_object(self, kind: str, external_id: str) -> _StoredObject | None:
        return self._objects.get((kind, external_id))

    @property
    def object_count(self) -> int:
        """Total provider objects created across every kind — the count a retry-after-failure
        test asserts stays at 1, proving no duplicate was created on the successful retry."""
        return len(self._objects)

    async def authenticate(self) -> bool:
        return self._authenticated

    async def sync_contact(self, *, external_id: str, fields: dict[str, Any]) -> CrmSyncResult:
        return await self._upsert("CONTACT", external_id, fields)

    async def sync_company(self, *, external_id: str, fields: dict[str, Any]) -> CrmSyncResult:
        return await self._upsert("COMPANY", external_id, fields)

    async def sync_opportunity(self, *, external_id: str, fields: dict[str, Any]) -> CrmSyncResult:
        return await self._upsert("OPPORTUNITY", external_id, fields)

    async def sync_task(self, *, external_id: str, fields: dict[str, Any]) -> CrmSyncResult:
        return await self._upsert("TASK", external_id, fields)

    async def _upsert(self, kind: str, external_id: str, fields: dict[str, Any]) -> CrmSyncResult:
        key = (kind, external_id)
        pending = self._pending_failures.get(key)
        if pending:
            raise pending.pop(0)

        existing = self._objects.get(key)
        if existing is not None:
            existing.fields = dict(fields)
            return CrmSyncResult(provider_object_id=existing.provider_object_id, created=False)

        provider_object_id = f"fake-{kind.lower()}-{self._next_id}"
        self._next_id += 1
        self._objects[key] = _StoredObject(
            provider_object_id=provider_object_id, fields=dict(fields)
        )
        return CrmSyncResult(provider_object_id=provider_object_id, created=True)
