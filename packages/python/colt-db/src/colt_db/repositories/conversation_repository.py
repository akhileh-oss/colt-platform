"""Tenant-scoped repository for `Conversation` (CLAUDE.md §10.12)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_db.mappers import conversation_to_domain
from colt_db.models.conversation import ConversationModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Conversation, ConversationState


class SqlAlchemyConversationRepository(TenantScopedRepository):
    async def add(
        self,
        *,
        lead_id: UUID,
        channel: str,
        state: ConversationState = ConversationState.OPEN,
        last_activity_at: datetime | None = None,
    ) -> Conversation:
        model = ConversationModel(
            organization_id=self.organization_id,
            lead_id=lead_id,
            channel=channel,
            state=state.value,
            last_activity_at=last_activity_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return conversation_to_domain(model)

    async def get(self, conversation_id: UUID) -> Conversation | None:
        stmt = self._select_scoped(ConversationModel).where(ConversationModel.id == conversation_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return conversation_to_domain(model) if model is not None else None
