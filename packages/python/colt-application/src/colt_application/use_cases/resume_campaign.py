"""`ResumeCampaign` (CLAUDE.md §10.9, Milestone 14).

Requires the campaign to specifically be `PAUSED`, not merely that `campaign_state.
can_transition` allows a move to `ACTIVE` — `DRAFT` also reaches `ACTIVE` in that table, but
only through `ValidateCampaign`, which re-checks the campaign's definition. Resuming a `DRAFT`
campaign would activate it without ever running those checks.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.errors import InvalidCampaignTransitionError, NotFoundError
from colt_application.ports.campaign_repository import CampaignRepository
from colt_domain import Campaign, CampaignStatus


class ResumeCampaign:
    def __init__(self, campaigns: CampaignRepository) -> None:
        self._campaigns = campaigns

    async def __call__(self, campaign_id: UUID, *, now: datetime) -> Campaign:
        campaign = await self._campaigns.get(campaign_id)
        if campaign is None:
            raise NotFoundError(f"No campaign found with id {campaign_id}.")
        if campaign.status is not CampaignStatus.PAUSED:
            raise InvalidCampaignTransitionError(campaign.status.value, CampaignStatus.ACTIVE.value)
        return await self._campaigns.update_status(campaign_id, CampaignStatus.ACTIVE, at=now)
