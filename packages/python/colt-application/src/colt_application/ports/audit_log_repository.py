"""The AuditLog repository port (CLAUDE.md §2.3, §48).

`SqlAlchemyAuditLogRepository` has existed as real infrastructure since Milestone 05, but no
use case has written through it until Milestone 16's `DecideMessageApproval`, `AddSuppressionEntry`
and `SendMessage` — this port is this milestone's own addition, not a gap carried from before.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from colt_domain import AuditLog


class AuditLogRepository(Protocol):
    async def record(
        self,
        *,
        actor_type: str,
        action: str,
        actor_id: UUID | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> AuditLog: ...
