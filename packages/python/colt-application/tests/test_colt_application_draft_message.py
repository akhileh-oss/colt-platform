"""`DraftMessage` (CLAUDE.md §10.11, §12.9, Milestone 15)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.errors import MessageValidationError
from colt_application.use_cases.draft_message import DraftMessage
from colt_domain import Evidence, Message

NOW = datetime.now(UTC)


class FakeEvidenceRepository:
    def __init__(self, evidence: list[Evidence]) -> None:
        self._by_id = {e.id: e for e in evidence}

    async def add(self, **kwargs: object) -> Evidence:
        raise NotImplementedError

    async def get(self, evidence_id: UUID) -> Evidence | None:
        return self._by_id.get(evidence_id)

    async def list_by_entity(self, entity_type: str, entity_id: UUID) -> list[Evidence]:
        raise NotImplementedError


class FakeMessageRepository:
    def __init__(self) -> None:
        self.added: list[Message] = []

    async def add(self, **kwargs: Any) -> Message:
        message = Message(
            id=uuid4(),
            organization_id=uuid4(),
            created_at=NOW,
            updated_at=NOW,
            **{k: v for k, v in kwargs.items() if v is not None},
        )
        self.added.append(message)
        return message

    async def get(self, message_id: UUID) -> Message | None:
        raise NotImplementedError

    async def get_by_idempotency_key(self, idempotency_key: str) -> Message | None:
        raise NotImplementedError

    async def get_by_provider_message_id(self, provider_message_id: str) -> Message | None:
        raise NotImplementedError

    async def list_by_campaign(self, campaign_id: UUID) -> list[Message]:
        raise NotImplementedError

    async def list_by_lead_and_step(
        self, lead_id: UUID, sequence_step_id: UUID | None
    ) -> list[Message]:
        return [
            m for m in self.added if m.lead_id == lead_id and m.sequence_step_id == sequence_step_id
        ]

    async def update_approval_status(self, message_id: UUID, *, approval_status: str) -> Message:
        raise NotImplementedError

    async def update_send_result(
        self,
        message_id: UUID,
        *,
        status: str,
        sent_at: datetime,
        provider_message_id: str | None,
        idempotency_key: str | None = None,
    ) -> Message:
        raise NotImplementedError

    async def count_sent_since(self, campaign_id: UUID, since: datetime) -> int:
        raise NotImplementedError


def _evidence() -> Evidence:
    return Evidence(
        id=uuid4(),
        organization_id=uuid4(),
        entity_type="Company",
        entity_id=uuid4(),
        claim="They raised a $20M Series B.",
        source_url="https://example.com/news",
        observed_at=NOW,
        created_at=NOW,
    )


@pytest.mark.asyncio
async def test_drafts_a_message_with_verified_evidence_ids() -> None:
    evidence = _evidence()
    messages = FakeMessageRepository()
    draft = DraftMessage(messages, FakeEvidenceRepository([evidence]))

    message = await draft(
        campaign_id=uuid4(),
        lead_id=uuid4(),
        channel="email",
        body="Congrats on the Series B - curious how you're scaling the team.",
        evidence_ids=[evidence.id],
    )

    assert message.evidence_ids == [evidence.id]
    assert message.status == "DRAFT"


@pytest.mark.asyncio
async def test_rejects_a_message_with_no_evidence_ids() -> None:
    draft = DraftMessage(FakeMessageRepository(), FakeEvidenceRepository([]))

    with pytest.raises(MessageValidationError):
        await draft(
            campaign_id=uuid4(), lead_id=uuid4(), channel="email", body="Hi there.", evidence_ids=[]
        )


@pytest.mark.asyncio
async def test_rejects_a_message_citing_evidence_that_does_not_exist() -> None:
    draft = DraftMessage(FakeMessageRepository(), FakeEvidenceRepository([]))

    with pytest.raises(MessageValidationError):
        await draft(
            campaign_id=uuid4(),
            lead_id=uuid4(),
            channel="email",
            body="Hi there.",
            evidence_ids=[uuid4()],
        )


@pytest.mark.asyncio
async def test_drafting_the_same_lead_and_step_twice_appends_a_new_version() -> None:
    evidence = _evidence()
    messages = FakeMessageRepository()
    draft = DraftMessage(messages, FakeEvidenceRepository([evidence]))
    lead_id = uuid4()
    step_id = uuid4()

    await draft(
        campaign_id=uuid4(),
        lead_id=lead_id,
        channel="email",
        body="First draft.",
        evidence_ids=[evidence.id],
        sequence_step_id=step_id,
    )
    await draft(
        campaign_id=uuid4(),
        lead_id=lead_id,
        channel="email",
        body="Second draft.",
        evidence_ids=[evidence.id],
        sequence_step_id=step_id,
    )

    versions = await messages.list_by_lead_and_step(lead_id, step_id)
    assert [v.body for v in versions] == ["First draft.", "Second draft."]
