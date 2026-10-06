"""`ProcessBounce` (CLAUDE.md §10.18, §18.1, §29, Milestone 17)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.use_cases.add_suppression_entry import AddSuppressionEntry
from colt_application.use_cases.process_bounce import ProcessBounce
from colt_domain import (
    AuditLog,
    Conversation,
    ConversationEvent,
    ConversationState,
    EmailStatus,
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
        self._message = message

    async def add(self, **kwargs: Any) -> Message:
        raise NotImplementedError

    async def get(self, message_id: UUID) -> Message | None:
        raise NotImplementedError

    async def get_by_idempotency_key(self, idempotency_key: str) -> Message | None:
        raise NotImplementedError

    async def get_by_provider_message_id(self, provider_message_id: str) -> Message | None:
        if self._message and self._message.provider_message_id == provider_message_id:
            return self._message
        return None

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

    async def get(self, lead_id: UUID) -> Lead | None:
        return self.lead if self.lead and lead_id == self.lead.id else None

    async def update_status(self, lead_id: UUID, status: LeadStatus, *, at: datetime) -> Lead:
        raise NotImplementedError


class FakePersonRepository:
    def __init__(self, person: Person | None) -> None:
        self.person = person
        self.updates: list[dict[str, Any]] = []

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
        assert self.person is not None
        self.updates.append(fields)
        self.person = self.person.model_copy(update=fields)
        return self.person


class FakeConversationRepository:
    def __init__(self, existing: Conversation | None = None) -> None:
        self.existing = existing
        self.added: list[Conversation] = []
        self.touched: list[UUID] = []

    async def add(self, **kwargs: Any) -> Conversation:
        conversation = Conversation(
            id=uuid4(), organization_id=uuid4(), created_at=NOW, updated_at=NOW, **kwargs
        )
        self.added.append(conversation)
        return conversation

    async def get(self, conversation_id: UUID) -> Conversation | None:
        raise NotImplementedError

    async def get_by_lead_and_channel(self, lead_id: UUID, channel: str) -> Conversation | None:
        return self.existing

    async def touch_last_activity(self, conversation_id: UUID, *, at: datetime) -> Conversation:
        self.touched.append(conversation_id)
        return (self.existing or self.added[-1]).model_copy(update={"last_activity_at": at})

    async def update_state(
        self, conversation_id: UUID, state: ConversationState, *, at: datetime
    ) -> Conversation:
        raise NotImplementedError


class FakeConversationEventRepository:
    def __init__(self) -> None:
        self.added: list[ConversationEvent] = []

    async def add(self, **kwargs: Any) -> ConversationEvent:
        event = ConversationEvent(id=uuid4(), organization_id=uuid4(), created_at=NOW, **kwargs)
        self.added.append(event)
        return event

    async def list_by_conversation(self, conversation_id: UUID) -> list[ConversationEvent]:
        raise NotImplementedError


class FakeSuppressionRepository:
    def __init__(self) -> None:
        self.added: list[SuppressionEntry] = []

    async def add(self, **kwargs: Any) -> SuppressionEntry:
        organization_scoped = kwargs.pop("organization_scoped", True)
        entry = SuppressionEntry(
            id=uuid4(),
            organization_id=uuid4() if organization_scoped else None,
            created_at=NOW,
            updated_at=NOW,
            **kwargs,
        )
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
        email="dana@bounced-domain.test",
        created_at=NOW,
        updated_at=NOW,
    )
    lead = Lead(
        id=uuid4(),
        organization_id=person.organization_id,
        company_id=person.company_id,
        person_id=person.id,
        created_at=NOW,
        updated_at=NOW,
    )
    return lead, person


def _sent_message(lead_id: UUID, provider_message_id: str) -> Message:
    return Message(
        id=uuid4(),
        organization_id=uuid4(),
        campaign_id=uuid4(),
        lead_id=lead_id,
        channel="email",
        body="Hello.",
        status="SENT",
        provider_message_id=provider_message_id,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_a_hard_bounce_suppresses_the_address_and_invalidates_the_email() -> None:
    lead, person = _lead_and_person()
    message = _sent_message(lead.id, "<bounced-1@colt.local>")
    messages = FakeMessageRepository(message)
    leads = FakeLeadRepository(lead)
    people = FakePersonRepository(person)
    conversations = FakeConversationRepository()
    conversation_events = FakeConversationEventRepository()
    suppressions = FakeSuppressionRepository()
    audit_logs = FakeAuditLogRepository()
    process_bounce = ProcessBounce(
        messages,
        leads,
        people,
        conversations,
        conversation_events,
        AddSuppressionEntry(suppressions, audit_logs),
    )

    event = await process_bounce(
        provider_message_id="<bounced-1@colt.local>", reason="hard_bounce", bounced_at=NOW
    )

    assert event.event_type == "bounced"
    (entry,) = suppressions.added
    assert entry.identifier == person.email
    assert entry.reason == SuppressionReason.BOUNCE
    assert people.updates == [{"email_status": EmailStatus.INVALID}]
    (created_conversation,) = conversations.added
    assert conversations.touched == [created_conversation.id]


@pytest.mark.asyncio
async def test_raises_not_found_when_the_bounced_message_is_unknown() -> None:
    messages = FakeMessageRepository(None)
    leads = FakeLeadRepository(None)
    people = FakePersonRepository(None)
    conversations = FakeConversationRepository()
    conversation_events = FakeConversationEventRepository()
    suppressions = FakeSuppressionRepository()
    audit_logs = FakeAuditLogRepository()
    process_bounce = ProcessBounce(
        messages,
        leads,
        people,
        conversations,
        conversation_events,
        AddSuppressionEntry(suppressions, audit_logs),
    )

    with pytest.raises(NotFoundError):
        await process_bounce(
            provider_message_id="<unknown@colt.local>", reason="hard_bounce", bounced_at=NOW
        )
