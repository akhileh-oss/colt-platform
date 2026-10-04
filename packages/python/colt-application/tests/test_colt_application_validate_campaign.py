"""`ValidateCampaign` (CLAUDE.md §10.9, Milestone 14)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import CampaignValidationError, InvalidCampaignTransitionError
from colt_application.use_cases.validate_campaign import ValidateCampaign
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


def _draft_campaign(**overrides: object) -> Campaign:
    base: dict[str, object] = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "name": "Q4 outbound",
        "status": CampaignStatus.DRAFT,
        "icp_definition": {"industry": "SaaS"},
        "channels": ["email"],
        "schedule": {"timezone": "UTC"},
        "limits": {"max_sends_per_day": 50},
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return Campaign(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_a_fully_configured_draft_campaign_becomes_active() -> None:
    campaign = _draft_campaign()
    campaigns = FakeCampaignRepository(campaign)
    validate_campaign = ValidateCampaign(campaigns)

    result = await validate_campaign(campaign.id, now=NOW)

    assert result.status == CampaignStatus.ACTIVE
    assert campaigns.status_updates == [CampaignStatus.ACTIVE]


@pytest.mark.asyncio
async def test_a_draft_campaign_missing_required_fields_stays_draft_and_raises() -> None:
    campaign = _draft_campaign(icp_definition={}, channels=[])
    campaigns = FakeCampaignRepository(campaign)
    validate_campaign = ValidateCampaign(campaigns)

    with pytest.raises(CampaignValidationError) as exc_info:
        await validate_campaign(campaign.id, now=NOW)

    assert len(exc_info.value.issues) == 2
    assert campaigns.status_updates == []


@pytest.mark.asyncio
async def test_validating_an_already_active_campaign_raises_without_re_checking_anything() -> None:
    campaign = _draft_campaign(status=CampaignStatus.ACTIVE)
    campaigns = FakeCampaignRepository(campaign)
    validate_campaign = ValidateCampaign(campaigns)

    with pytest.raises(InvalidCampaignTransitionError):
        await validate_campaign(campaign.id, now=NOW)


@pytest.mark.asyncio
async def test_validating_a_paused_campaign_raises_rather_than_resurrecting_it() -> None:
    """A `PAUSED` campaign can reach `ACTIVE` too, but only through `ResumeCampaign` — this use
    case must not let it in through a different door."""
    campaign = _draft_campaign(status=CampaignStatus.PAUSED)
    campaigns = FakeCampaignRepository(campaign)
    validate_campaign = ValidateCampaign(campaigns)

    with pytest.raises(InvalidCampaignTransitionError):
        await validate_campaign(campaign.id, now=NOW)
