"""The CRMProvider port (CLAUDE.md §30, §28.2, Milestone 20).

CLAUDE.md names `CRMProvider` as the adapter and "contact sync," "company sync," "opportunity
sync," and "task sync" as separate Build items, but no specific real CRM vendor (unlike
`SearchProvider`/`EnrichmentProvider`, both named in §28.2) — the same situation
`SignalTriggerSource` (Milestone 12) was in. Only the port and its fake are built this milestone;
a real adapter (a specific CRM vendor) is a natural follow-up once one is chosen, not a gap in
this one.

Every sync call is keyed by `external_id` — the calling Colt entity's own id as a string — so a
retry of the same entity always targets the same provider object rather than creating a
duplicate (CLAUDE.md §30's "CRM sync must be idempotent").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class CrmSyncResult:
    provider_object_id: str
    created: bool


class CRMProvider(Protocol):
    async def authenticate(self) -> bool: ...

    async def sync_contact(self, *, external_id: str, fields: dict[str, Any]) -> CrmSyncResult: ...

    async def sync_company(self, *, external_id: str, fields: dict[str, Any]) -> CrmSyncResult: ...

    async def sync_opportunity(
        self, *, external_id: str, fields: dict[str, Any]
    ) -> CrmSyncResult: ...

    async def sync_task(self, *, external_id: str, fields: dict[str, Any]) -> CrmSyncResult: ...
