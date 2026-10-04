"""The Signal repository port (CLAUDE.md §2.3, §10.5).

Tenant-scoped, like `EvidenceRepository`: an implementation is bound to one `organization_id`
at construction.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from colt_domain import Signal


class SignalRepository(Protocol):
    async def add(
        self,
        *,
        company_id: UUID,
        signal_type: str,
        observed_at: datetime,
        person_id: UUID | None = None,
        source_url: str | None = None,
        source_type: str | None = None,
        event_at: datetime | None = None,
        confidence: float | None = None,
        summary: str | None = None,
        business_implication: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> Signal: ...

    async def get(self, signal_id: UUID) -> Signal | None: ...
