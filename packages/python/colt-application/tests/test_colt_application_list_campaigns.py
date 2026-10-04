"""`ListCampaigns` (CLAUDE.md §10.9, Milestone 14)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.use_cases.list_campaigns import ListCampaigns
from colt_domain import Campaign, CampaignStatus

NOW = datetime.now(UTC)


class FakeCampaignRepository:
    def __init__(self, campaigns: list[Campaign]) -> None:
        self._campaigns = campaigns

    async def add(self, **kwargs: object) -> Campaign:
        raise NotImplementedError

    async def get(self, campaign_id: UUID) -> Campaign | None:
        raise NotImplementedError

    async def list_all(self) -> list[Campaign]:
        return list(self._campaigns)

    async def update_status(
        self, campaign_id: UUID, status: CampaignStatus, *, at: datetime
    ) -> Campaign:
        raise NotImplementedError


def _campaign(name: str) -> Campaign:
    return Campaign(id=uuid4(), organization_id=uuid4(), name=name, created_at=NOW, updated_at=NOW)


@pytest.mark.asyncio
async def test_lists_every_campaign_in_this_organization() -> None:
    campaigns = [_campaign("First"), _campaign("Second")]
    list_campaigns = ListCampaigns(FakeCampaignRepository(campaigns))

    result = await list_campaigns()

    assert result == campaigns


@pytest.mark.asyncio
async def test_returns_an_empty_list_when_the_organization_has_no_campaigns() -> None:
    list_campaigns = ListCampaigns(FakeCampaignRepository([]))

    assert await list_campaigns() == []
