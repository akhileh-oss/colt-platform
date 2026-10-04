"""`PauseCampaign` (CLAUDE.md §10.9, Milestone 14)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.campaign_state import can_transition
from colt_application.errors import InvalidCampaignTransitionError, NotFoundError
from colt_application.ports.campaign_repository import CampaignRepository
from colt_domain import Campaign, CampaignStatus


class PauseCampaign:
    def __init__(self, campaigns: CampaignRepository) -> None:
        self._campaigns = campaigns

    async def __call__(self, campaign_id: UUID, *, now: datetime) -> Campaign:
        campaign = await self._campaigns.get(campaign_id)
        if campaign is None:
            raise NotFoundError(f"No campaign found with id {campaign_id}.")
        if not can_transition(campaign.status, CampaignStatus.PAUSED):
            raise InvalidCampaignTransitionError(campaign.status.value, CampaignStatus.PAUSED.value)
        return await self._campaigns.update_status(campaign_id, CampaignStatus.PAUSED, at=now)
