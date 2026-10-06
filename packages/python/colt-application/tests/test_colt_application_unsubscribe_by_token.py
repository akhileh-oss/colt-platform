"""`UnsubscribeByToken` (CLAUDE.md §10.18, §18.1, §18.2, §29, Milestone 17)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.use_cases.add_suppression_entry import AddSuppressionEntry
from colt_application.use_cases.unsubscribe_by_token import UnsubscribeByToken
from colt_domain import (
    AuditLog,
    Conversation,
    ConversationState,
    Lead,
    LeadStatus,
    Message,
    Person,
    SuppressionEntry,
    SuppressionReason,
)

NOW = datetime.now(UTC)


class FakeMessageRepository:
    def __init__(self, message: Message | None) -> None:
        self.message = message

    async def add(self, **kwargs: Any) -> Message:
        raise NotImplementedError

    async def get(self, message_id: UUID) -> Message | None:
        return self.message if self.message and message_id == self.message.id else None

    async def get_by_idempotency_key(self, idempotency_key: str) -> Message | None:
        raise NotImplementedError

    async def get_by_provider_message_id(self, provider_message_id: str) -> Message | None:
        raise NotImplementedError

    async def list_by_campaign(self, campaign_id: UUID) -> list[Message]:
        raise NotImplementedError

    async def list_by_lead_and_step(
        self, lead_id: UUID, sequence_step_id: UUID | None
    ) -> list[Message]:
        raise NotImplementedError

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


class FakeLeadRepository:
    def __init__(self, lead: Lead | None) -> None:
        self.lead = lead
        self.status_updates: list[LeadStatus] = []

    async def get(self, lead_id: UUID) -> Lead | None:
        return self.lead if self.lead and lead_id == self.lead.id else None

    async def update_status(self, lead_id: UUID, status: LeadStatus, *, at: datetime) -> Lead:
        assert self.lead is not None
        self.status_updates.append(status)
        self.lead = self.lead.with_status(status, at=at)
        return self.lead


class FakePersonRepository:
    def __init__(self, person: Person | None) -> None:
        self.person = person

    async def add(self, **kwargs: Any) -> Person:
        raise NotImplementedError

    async def get(self, person_id: UUID) -> Person | None:
        return self.person if self.person and person_id == self.person.id else None

    async def find_by_email(self, email: str) -> Person | None:
        raise NotImplementedError

    async def find_by_linkedin_url(self, linkedin_url: str) -> Person | None:
        raise NotImplementedError

    async def list_by_company(self, company_id: UUID) -> list[Person]:
        raise NotImplementedError

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Person | None:
        raise NotImplementedError

    async def update(self, person_id: UUID, **fields: Any) -> Person:
        raise NotImplementedError


class FakeConversationRepository:
    def __init__(self, existing: Conversation | None = None) -> None:
        self.existing = existing
        self.state_updates: list[ConversationState] = []

    async def add(self, **kwargs: Any) -> Conversation:
        raise NotImplementedError

    async def get(self, conversation_id: UUID) -> Conversation | None:
        raise NotImplementedError

    async def get_by_lead_and_channel(self, lead_id: UUID, channel: str) -> Conversation | None:
        return self.existing

    async def touch_last_activity(self, conversation_id: UUID, *, at: datetime) -> Conversation:
        raise NotImplementedError

    async def update_state(
        self, conversation_id: UUID, state: ConversationState, *, at: datetime
    ) -> Conversation:
        assert self.existing is not None
        self.state_updates.append(state)
        self.existing = self.existing.with_state(state, at=at)
        return self.existing


class FakeSuppressionRepository:
    def __init__(self) -> None:
        self.added: list[SuppressionEntry] = []

    async def add(self, **kwargs: Any) -> SuppressionEntry:
        kwargs.pop("organization_scoped", True)
        entry = SuppressionEntry(id=uuid4(), created_at=NOW, updated_at=NOW, **kwargs)
        self.added.append(entry)
        return entry

    async def is_suppressed(self, identifier_type: str, identifier: str) -> bool:
        raise NotImplementedError

    async def get(self, suppression_entry_id: UUID) -> SuppressionEntry | None:
        raise NotImplementedError


class FakeAuditLogRepository:
    def __init__(self) -> None:
        self.recorded: list[AuditLog] = []

    async def record(self, **kwargs: Any) -> AuditLog:
        log = AuditLog(id=uuid4(), organization_id=uuid4(), created_at=NOW, **kwargs)
        self.recorded.append(log)
        return log


def _lead_and_person() -> tuple[Lead, Person]:
    person = Person(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        full_name="Dana Prospect",
        email="dana@example.com",
        created_at=NOW,
        updated_at=NOW,
    )
    lead = Lead(
        id=uuid4(),
        organization_id=person.organization_id,
        company_id=person.company_id,
        person_id=person.id,
        status=LeadStatus.CONTACTED,
        created_at=NOW,
        updated_at=NOW,
    )
    return lead, person


def _message(lead_id: UUID) -> Message:
    return Message(
        id=uuid4(),
        organization_id=uuid4(),
        campaign_id=uuid4(),
        lead_id=lead_id,
        channel="email",
        body="Hello.",
        status="SENT",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_unsubscribing_suppresses_the_address_and_terminates_the_conversation() -> None:
    lead, person = _lead_and_person()
    message = _message(lead.id)
    conversation = Conversation(
        id=uuid4(),
        organization_id=lead.organization_id,
        lead_id=lead.id,
        channel="email",
        created_at=NOW,
        updated_at=NOW,
    )
    messages = FakeMessageRepository(message)
    leads = FakeLeadRepository(lead)
    people = FakePersonRepository(person)
    conversations = FakeConversationRepository(existing=conversation)
    suppressions = FakeSuppressionRepository()
    audit_logs = FakeAuditLogRepository()
    unsubscribe = UnsubscribeByToken(
        messages, leads, people, conversations, AddSuppressionEntry(suppressions, audit_logs)
    )

    updated_lead = await unsubscribe(message_id=message.id, unsubscribed_at=NOW)

    assert updated_lead.status == LeadStatus.UNSUBSCRIBED
    (entry,) = suppressions.added
    assert entry.identifier == person.email
    assert entry.reason == SuppressionReason.UNSUBSCRIBE
    assert conversations.state_updates == [ConversationState.UNSUBSCRIBED]


@pytest.mark.asyncio
async def test_unsubscribing_with_no_open_conversation_still_suppresses_the_lead() -> None:
    lead, person = _lead_and_person()
    message = _message(lead.id)
    messages = FakeMessageRepository(message)
    leads = FakeLeadRepository(lead)
    people = FakePersonRepository(person)
    conversations = FakeConversationRepository(existing=None)
    suppressions = FakeSuppressionRepository()
    audit_logs = FakeAuditLogRepository()
    unsubscribe = UnsubscribeByToken(
        messages, leads, people, conversations, AddSuppressionEntry(suppressions, audit_logs)
    )

    updated_lead = await unsubscribe(message_id=message.id, unsubscribed_at=NOW)

    assert updated_lead.status == LeadStatus.UNSUBSCRIBED
    assert len(suppressions.added) == 1


@pytest.mark.asyncio
async def test_raises_not_found_for_an_unknown_message_token() -> None:
    messages = FakeMessageRepository(None)
    leads = FakeLeadRepository(None)
    people = FakePersonRepository(None)
    conversations = FakeConversationRepository()
    suppressions = FakeSuppressionRepository()
    audit_logs = FakeAuditLogRepository()
    unsubscribe = UnsubscribeByToken(
        messages, leads, people, conversations, AddSuppressionEntry(suppressions, audit_logs)
    )

    with pytest.raises(NotFoundError):
        await unsubscribe(message_id=uuid4(), unsubscribed_at=NOW)
