"""`GetCampaign` (CLAUDE.md §10.9, Milestone 14) — the "inspected" half of this milestone's
acceptance criterion."""

from __future__ import annotations

from uuid import UUID

from colt_application.errors import NotFoundError
from colt_application.ports.campaign_repository import CampaignRepository
from colt_domain import Campaign


class GetCampaign:
    def __init__(self, campaigns: CampaignRepository) -> None:
        self._campaigns = campaigns

    async def __call__(self, campaign_id: UUID) -> Campaign:
        campaign = await self._campaigns.get(campaign_id)
        if campaign is None:
            raise NotFoundError(f"No campaign found with id {campaign_id}.")
        return campaign
