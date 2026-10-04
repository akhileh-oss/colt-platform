"""`ListSequenceSteps` (CLAUDE.md §10.9, §10.10, Milestone 14)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.use_cases.list_sequence_steps import ListSequenceSteps
from colt_domain import Campaign, CampaignStatus, SequenceStep

NOW = datetime.now(UTC)


class FakeCampaignRepository:
    def __init__(self, campaign: Campaign | None) -> None:
        self.campaign = campaign

    async def add(self, **kwargs: object) -> Campaign:
        raise NotImplementedError

    async def get(self, campaign_id: UUID) -> Campaign | None:
        return self.campaign if self.campaign and campaign_id == self.campaign.id else None

    async def list_all(self) -> list[Campaign]:
        raise NotImplementedError

    async def update_status(
        self, campaign_id: UUID, status: CampaignStatus, *, at: datetime
    ) -> Campaign:
        raise NotImplementedError


class FakeSequenceStepRepository:
    def __init__(self, steps: list[SequenceStep]) -> None:
        self._steps = steps

    async def add(self, **kwargs: object) -> SequenceStep:
        raise NotImplementedError

    async def get(self, sequence_step_id: UUID) -> SequenceStep | None:
        raise NotImplementedError

    async def list_by_campaign(self, campaign_id: UUID) -> list[SequenceStep]:
        return [s for s in self._steps if s.campaign_id == campaign_id]


def _campaign() -> Campaign:
    return Campaign(
        id=uuid4(), organization_id=uuid4(), name="Q4 outbound", created_at=NOW, updated_at=NOW
    )


def _step(campaign_id: UUID, order: int) -> SequenceStep:
    return SequenceStep(
        id=uuid4(),
        organization_id=uuid4(),
        campaign_id=campaign_id,
        step_order=order,
        channel="email",
        message_strategy="Lead with the funding-round signal.",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_lists_every_step_of_an_existing_campaign() -> None:
    campaign = _campaign()
    steps = [_step(campaign.id, 0), _step(campaign.id, 1)]
    list_steps = ListSequenceSteps(
        FakeCampaignRepository(campaign), FakeSequenceStepRepository(steps)
    )

    result = await list_steps(campaign.id)

    assert result == steps


@pytest.mark.asyncio
async def test_raises_not_found_for_a_campaign_outside_this_organization() -> None:
    list_steps = ListSequenceSteps(FakeCampaignRepository(None), FakeSequenceStepRepository([]))

    with pytest.raises(NotFoundError):
        await list_steps(uuid4())
