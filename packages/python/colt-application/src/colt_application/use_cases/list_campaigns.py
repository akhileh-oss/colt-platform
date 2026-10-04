"""`ListCampaigns` (CLAUDE.md §10.9, Milestone 14)."""

from __future__ import annotations

from colt_application.ports.campaign_repository import CampaignRepository
from colt_domain import Campaign


class ListCampaigns:
    def __init__(self, campaigns: CampaignRepository) -> None:
        self._campaigns = campaigns

    async def __call__(self) -> list[Campaign]:
        return await self._campaigns.list_all()
