"""The ConversationEvent repository port (CLAUDE.md §2.3, §10.13)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from colt_domain import ConversationEvent


class ConversationEventRepository(Protocol):
    async def add(
        self,
        *,
        conversation_id: UUID,
        event_type: str,
        occurred_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationEvent: ...

    async def list_by_conversation(self, conversation_id: UUID) -> list[ConversationEvent]: ...
