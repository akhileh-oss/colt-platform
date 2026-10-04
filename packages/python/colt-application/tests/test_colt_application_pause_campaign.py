"""`PauseCampaign` (CLAUDE.md §10.9, Milestone 14)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import InvalidCampaignTransitionError
from colt_application.use_cases.pause_campaign import PauseCampaign
from colt_domain import Campaign, CampaignStatus

NOW = datetime.now(UTC)


class FakeCampaignRepository:
    def __init__(self, campaign: Campaign) -> None:
        self.campaign = campaign
        self.status_updates: list[CampaignStatus] = []

    async def add(self, **kwargs: object) -> Campaign:
        raise NotImplementedError

    async def get(self, campaign_id: UUID) -> Campaign | None:
        return self.campaign if campaign_id == self.campaign.id else None

    async def list_all(self) -> list[Campaign]:
        raise NotImplementedError

    async def update_status(
        self, campaign_id: UUID, status: CampaignStatus, *, at: datetime
    ) -> Campaign:
        self.status_updates.append(status)
        self.campaign = self.campaign.model_copy(update={"status": status, "updated_at": at})
        return self.campaign


def _campaign(status: CampaignStatus) -> Campaign:
    return Campaign(
        id=uuid4(),
        organization_id=uuid4(),
        name="Q4 outbound",
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_an_active_campaign_can_be_paused() -> None:
    campaign = _campaign(CampaignStatus.ACTIVE)
    campaigns = FakeCampaignRepository(campaign)
    pause_campaign = PauseCampaign(campaigns)

    result = await pause_campaign(campaign.id, now=NOW)

    assert result.status == CampaignStatus.PAUSED


@pytest.mark.asyncio
async def test_a_draft_campaign_cannot_be_paused() -> None:
    campaign = _campaign(CampaignStatus.DRAFT)
    campaigns = FakeCampaignRepository(campaign)
    pause_campaign = PauseCampaign(campaigns)

    with pytest.raises(InvalidCampaignTransitionError):
        await pause_campaign(campaign.id, now=NOW)


@pytest.mark.asyncio
async def test_an_already_paused_campaign_cannot_be_paused_again() -> None:
    campaign = _campaign(CampaignStatus.PAUSED)
    campaigns = FakeCampaignRepository(campaign)
    pause_campaign = PauseCampaign(campaigns)

    with pytest.raises(InvalidCampaignTransitionError):
        await pause_campaign(campaign.id, now=NOW)
