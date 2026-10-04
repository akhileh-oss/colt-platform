"""`CreateCampaign` (CLAUDE.md §10.9, Milestone 14)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.use_cases.create_campaign import CreateCampaign
from colt_domain import Campaign, CampaignStatus

NOW = datetime.now(UTC)


class FakeCampaignRepository:
    def __init__(self) -> None:
        self.added: list[Campaign] = []

    async def add(self, **kwargs: Any) -> Campaign:
        campaign = Campaign(
            id=uuid4(),
            organization_id=uuid4(),
            created_at=NOW,
            updated_at=NOW,
            **{k: v for k, v in kwargs.items() if v is not None},
        )
        self.added.append(campaign)
        return campaign

    async def get(self, campaign_id: UUID) -> Campaign | None:
        return next((c for c in self.added if c.id == campaign_id), None)

    async def list_all(self) -> list[Campaign]:
        return list(self.added)

    async def update_status(
        self, campaign_id: UUID, status: CampaignStatus, *, at: datetime
    ) -> Campaign:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_a_created_campaign_always_starts_in_draft() -> None:
    campaigns = FakeCampaignRepository()
    create_campaign = CreateCampaign(campaigns)

    campaign = await create_campaign(
        name="Q4 outbound",
        icp_definition={"industry": "SaaS"},
        channels=["email"],
        schedule={"timezone": "UTC"},
        limits={"max_sends_per_day": 50},
    )

    assert campaign.status == CampaignStatus.DRAFT
    assert campaign.name == "Q4 outbound"
    assert campaigns.added == [campaign]


@pytest.mark.asyncio
async def test_create_campaign_accepts_a_minimal_definition() -> None:
    campaigns = FakeCampaignRepository()
    create_campaign = CreateCampaign(campaigns)

    campaign = await create_campaign(name="Bare draft")

    assert campaign.status == CampaignStatus.DRAFT
    assert campaign.icp_definition == {}
    assert campaign.channels == []
