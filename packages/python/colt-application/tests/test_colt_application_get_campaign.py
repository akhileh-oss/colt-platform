"""`GetCampaign` (CLAUDE.md §10.9, Milestone 14)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.use_cases.get_campaign import GetCampaign
from colt_domain import Campaign, CampaignStatus

NOW = datetime.now(UTC)


class FakeCampaignRepository:
    """Only `get` is exercised; the rest exist purely so this structurally satisfies the
    `CampaignRepository` port."""

    def __init__(self, campaigns: list[Campaign]) -> None:
        self._by_id = {campaign.id: campaign for campaign in campaigns}

    async def add(self, **kwargs: object) -> Campaign:
        raise NotImplementedError

    async def get(self, campaign_id: UUID) -> Campaign | None:
        return self._by_id.get(campaign_id)

    async def list_all(self) -> list[Campaign]:
        raise NotImplementedError

    async def update_status(
        self, campaign_id: UUID, status: CampaignStatus, *, at: datetime
    ) -> Campaign:
        raise NotImplementedError


def _campaign(*, id: UUID | None = None) -> Campaign:
    return Campaign(
        id=id or uuid4(),
        organization_id=uuid4(),
        name="Q4 outbound",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_returns_the_campaign_when_it_exists_in_this_organization() -> None:
    campaign = _campaign()
    get_campaign = GetCampaign(FakeCampaignRepository([campaign]))

    result = await get_campaign(campaign.id)

    assert result.id == campaign.id


@pytest.mark.asyncio
async def test_raises_not_found_when_the_campaign_does_not_exist_in_this_organization() -> None:
    get_campaign = GetCampaign(FakeCampaignRepository([]))

    with pytest.raises(NotFoundError):
        await get_campaign(uuid4())
