"""`ListMessages` (CLAUDE.md §10.11, Milestone 15)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.use_cases.list_messages import ListMessages
from colt_domain import Campaign, Message

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

    async def update_status(self, campaign_id: UUID, status: object, *, at: datetime) -> Campaign:
        raise NotImplementedError


class FakeMessageRepository:
    def __init__(self, messages: list[Message]) -> None:
        self._messages = messages

    async def add(self, **kwargs: object) -> Message:
        raise NotImplementedError

    async def get(self, message_id: UUID) -> Message | None:
        raise NotImplementedError

    async def get_by_idempotency_key(self, idempotency_key: str) -> Message | None:
        raise NotImplementedError

    async def list_by_campaign(self, campaign_id: UUID) -> list[Message]:
        return [m for m in self._messages if m.campaign_id == campaign_id]

    async def list_by_lead_and_step(
        self, lead_id: UUID, sequence_step_id: UUID | None
    ) -> list[Message]:
        raise NotImplementedError


def _campaign() -> Campaign:
    return Campaign(
        id=uuid4(), organization_id=uuid4(), name="Q4 outbound", created_at=NOW, updated_at=NOW
    )


def _message(campaign_id: UUID) -> Message:
    return Message(
        id=uuid4(),
        organization_id=uuid4(),
        campaign_id=campaign_id,
        lead_id=uuid4(),
        channel="email",
        body="Hello.",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_lists_every_message_of_an_existing_campaign() -> None:
    campaign = _campaign()
    messages = [_message(campaign.id), _message(campaign.id)]
    list_messages = ListMessages(FakeCampaignRepository(campaign), FakeMessageRepository(messages))

    result = await list_messages(campaign.id)

    assert result == messages


@pytest.mark.asyncio
async def test_raises_not_found_for_a_campaign_outside_this_organization() -> None:
    list_messages = ListMessages(FakeCampaignRepository(None), FakeMessageRepository([]))

    with pytest.raises(NotFoundError):
        await list_messages(uuid4())
