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

    async def get_by_lead_and_channel(self, lead_id: UUID, channel: str) -> Conversation | None:
        """The one open thread a lead has per channel — what inbound reply ingestion (§29.1)
        resolves an incoming message to."""
        stmt = self._select_scoped(ConversationModel).where(
            ConversationModel.lead_id == lead_id, ConversationModel.channel == channel
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return conversation_to_domain(model) if model is not None else None

    async def list_all(self) -> list[Conversation]:
        """Every conversation in this organization — the channel-performance analytics read
        model (Milestone 22) groups over this by `channel`/`state`."""
        stmt = self._select_scoped(ConversationModel)
        models = (await self._session.execute(stmt)).scalars().all()
        return [conversation_to_domain(model) for model in models]

    async def touch_last_activity(self, conversation_id: UUID, *, at: datetime) -> Conversation:
        stmt = self._select_scoped(ConversationModel).where(ConversationModel.id == conversation_id)
        model = (await self._session.execute(stmt)).scalar_one()
        model.last_activity_at = at
        await self._session.flush()
        await self._session.refresh(model)
        return conversation_to_domain(model)

    async def update_state(
        self, conversation_id: UUID, state: ConversationState, *, at: datetime
    ) -> Conversation:
        stmt = self._select_scoped(ConversationModel).where(ConversationModel.id == conversation_id)
        model = (await self._session.execute(stmt)).scalar_one()
        model.state = state.value
        model.updated_at = at
        await self._session.flush()
        await self._session.refresh(model)
        return conversation_to_domain(model)
