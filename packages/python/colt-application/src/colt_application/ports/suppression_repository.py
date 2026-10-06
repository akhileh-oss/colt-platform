"""The Suppression repository port (CLAUDE.md §2.3, §10.18, §18.1)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from colt_domain import SuppressionEntry, SuppressionReason


class SuppressionRepository(Protocol):
    async def add(
        self,
        *,
        identifier_type: str,
        identifier: str,
        reason: SuppressionReason,
        source: str,
        organization_scoped: bool = True,
    ) -> SuppressionEntry: ...

    async def is_suppressed(self, identifier_type: str, identifier: str) -> bool: ...

    async def get(self, suppression_entry_id: UUID) -> SuppressionEntry | None: ...
