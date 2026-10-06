"""`AddSuppressionEntry` (CLAUDE.md §10.18, §18.1, §18.2, §48, Milestone 16).

"A recognized unsubscribe must: ... create/update suppression state; ... generate an audit
event" (§18.2) — this use case is that mechanism for every §10.18 reason, not only unsubscribe.
"""

from __future__ import annotations

from uuid import UUID

from colt_application.ports.audit_log_repository import AuditLogRepository
from colt_application.ports.suppression_repository import SuppressionRepository
from colt_domain import SuppressionEntry, SuppressionReason


class AddSuppressionEntry:
    def __init__(self, suppressions: SuppressionRepository, audit_logs: AuditLogRepository) -> None:
        self._suppressions = suppressions
        self._audit_logs = audit_logs

    async def __call__(
        self,
        *,
        identifier_type: str,
        identifier: str,
        reason: SuppressionReason,
        source: str,
        organization_scoped: bool = True,
        actor_id: UUID | None = None,
    ) -> SuppressionEntry:
        entry = await self._suppressions.add(
            identifier_type=identifier_type,
            identifier=identifier,
            reason=reason,
            source=source,
            organization_scoped=organization_scoped,
        )
        await self._audit_logs.record(
            actor_type="user" if actor_id is not None else "system",
            actor_id=actor_id,
            action="suppression_added",
            entity_type="SuppressionEntry",
            entity_id=entry.id,
            metadata={
                "identifier_type": identifier_type,
                "reason": reason.value,
                "organization_scoped": organization_scoped,
            },
        )
        return entry
