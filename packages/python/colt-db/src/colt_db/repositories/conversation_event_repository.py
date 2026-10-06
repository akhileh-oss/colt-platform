"""Tenant-scoped repository for `ConversationEvent` (CLAUDE.md §10.13). Append-only: no update
or delete method, the same pattern `SqlAlchemyAuditLogRepository` (§48) already establishes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from colt_db.mappers import conversation_event_to_domain
from colt_db.models.conversation_event import ConversationEventModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import ConversationEvent


class SqlAlchemyConversationEventRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        conversation_id: UUID,
        event_type: str,
        occurred_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationEvent:
        model = ConversationEventModel(
            organization_id=self.organization_id,
            conversation_id=conversation_id,
            event_type=event_type,
            event_metadata=metadata or {},
            occurred_at=occurred_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return conversation_event_to_domain(model)

    async def list_by_conversation(self, conversation_id: UUID) -> list[ConversationEvent]:
        stmt = (
            self._select_scoped(ConversationEventModel)
            .where(ConversationEventModel.conversation_id == conversation_id)
            .order_by(ConversationEventModel.occurred_at)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [conversation_event_to_domain(model) for model in models]
