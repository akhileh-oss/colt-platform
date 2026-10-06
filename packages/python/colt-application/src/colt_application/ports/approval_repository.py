"""The Approval repository port (CLAUDE.md §2.3, §10.17)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from colt_domain import Approval, ApprovalStatus


class ApprovalRepository(Protocol):
    async def add(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        action_type: str,
        requested_by: UUID | None = None,
    ) -> Approval: ...

    async def get(self, approval_id: UUID) -> Approval | None: ...

    async def get_latest_for_entity(self, entity_type: str, entity_id: UUID) -> Approval | None: ...

    async def decide(
        self,
        approval_id: UUID,
        *,
        status: ApprovalStatus,
        approved_by: UUID,
        reason: str | None,
        decided_at: datetime,
    ) -> Approval: ...
