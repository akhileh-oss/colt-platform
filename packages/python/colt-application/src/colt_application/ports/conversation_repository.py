"""The Conversation repository port (CLAUDE.md §2.3, §10.12).

`SqlAlchemyConversationRepository` has existed as real infrastructure since Milestone 05, but
no use case has needed it until Milestone 17's `ProcessInboundEmail` — this port is this
milestone's own addition, not a gap carried from before.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from colt_domain import Conversation, ConversationState


class ConversationRepository(Protocol):
    async def add(
        self,
        *,
        lead_id: UUID,
        channel: str,
        state: ConversationState = ConversationState.OPEN,
        last_activity_at: datetime | None = None,
    ) -> Conversation: ...

    async def get(self, conversation_id: UUID) -> Conversation | None: ...

    async def get_by_lead_and_channel(self, lead_id: UUID, channel: str) -> Conversation | None: ...

    async def touch_last_activity(self, conversation_id: UUID, *, at: datetime) -> Conversation: ...

    async def update_state(
        self, conversation_id: UUID, state: ConversationState, *, at: datetime
    ) -> Conversation: ...
