"""`ListMessages` (CLAUDE.md §10.11, Milestone 15) — the read path the message review UI calls.

Checks the campaign exists first, same reasoning as `ListSequenceSteps`: otherwise an unknown
`campaign_id` and a real campaign with no drafted messages yet both return an empty list,
indistinguishably.
"""

from __future__ import annotations

from uuid import UUID

from colt_application.errors import NotFoundError
from colt_application.ports.campaign_repository import CampaignRepository
from colt_application.ports.message_repository import MessageRepository
from colt_domain import Message


class ListMessages:
    def __init__(self, campaigns: CampaignRepository, messages: MessageRepository) -> None:
        self._campaigns = campaigns
        self._messages = messages

    async def __call__(self, campaign_id: UUID) -> list[Message]:
        if await self._campaigns.get(campaign_id) is None:
            raise NotFoundError(f"No campaign found with id {campaign_id}.")
        return await self._messages.list_by_campaign(campaign_id)
