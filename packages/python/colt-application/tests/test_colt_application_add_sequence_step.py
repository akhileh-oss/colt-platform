"""`AddSequenceStep` (CLAUDE.md §10.9, §10.10, Milestone 14)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.use_cases.add_sequence_step import AddSequenceStep
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
    def __init__(self) -> None:
        self.added: list[SequenceStep] = []

    async def add(self, **kwargs: Any) -> SequenceStep:
        step = SequenceStep(
            id=uuid4(),
            organization_id=uuid4(),
            created_at=NOW,
            updated_at=NOW,
            **{k: v for k, v in kwargs.items() if v is not None},
        )
        self.added.append(step)
        return step

    async def get(self, sequence_step_id: UUID) -> SequenceStep | None:
        return next((s for s in self.added if s.id == sequence_step_id), None)

    async def list_by_campaign(self, campaign_id: UUID) -> list[SequenceStep]:
        return [s for s in self.added if s.campaign_id == campaign_id]


def _campaign() -> Campaign:
    return Campaign(
        id=uuid4(), organization_id=uuid4(), name="Q4 outbound", created_at=NOW, updated_at=NOW
    )


@pytest.mark.asyncio
async def test_adds_a_step_to_an_existing_campaign() -> None:
    campaign = _campaign()
    sequence_steps = FakeSequenceStepRepository()
    add_step = AddSequenceStep(FakeCampaignRepository(campaign), sequence_steps)

    step = await add_step(
        campaign_id=campaign.id,
        step_order=0,
        channel="email",
        message_strategy="Lead with the funding-round signal.",
    )

    assert step.campaign_id == campaign.id
    assert step.step_order == 0
    assert sequence_steps.added == [step]


@pytest.mark.asyncio
async def test_raises_not_found_for_a_campaign_outside_this_organization() -> None:
    sequence_steps = FakeSequenceStepRepository()
    add_step = AddSequenceStep(FakeCampaignRepository(None), sequence_steps)

    with pytest.raises(NotFoundError):
        await add_step(
            campaign_id=uuid4(),
            step_order=0,
            channel="email",
            message_strategy="Lead with the funding-round signal.",
        )

    assert sequence_steps.added == []
