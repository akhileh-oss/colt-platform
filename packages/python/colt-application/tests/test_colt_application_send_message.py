"""`SendMessage` (CLAUDE.md §17, §17.1, §18, Milestone 16) — the literal mechanism behind this
milestone's acceptance criterion: "a policy violation cannot result in an external message
send." Every denial-path test below asserts the fake sender was never called, not just that an
error was raised — the thing CLAUDE.md actually asks to be proven.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError, PolicyDeniedError
from colt_application.use_cases.send_message import SendMessage
from colt_domain import (
    Approval,
    ApprovalStatus,
    AuditLog,
    Campaign,
    CampaignStatus,
    EmailStatus,
    Evidence,
    Lead,
    LeadStatus,
    Message,
    Person,
)

NOW = datetime.now(UTC)


class FakeMessageRepository:
    def __init__(self, message: Message) -> None:
        self.message = message
        self.sent_count = 0

    async def add(self, **kwargs: Any) -> Message:
        raise NotImplementedError

    async def get(self, message_id: UUID) -> Message | None:
        return self.message if message_id == self.message.id else None

    async def get_by_idempotency_key(self, idempotency_key: str) -> Message | None:
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
        self, message_id: UUID, *, status: str, sent_at: datetime, provider_message_id: str | None
    ) -> Message:
        self.message = self.message.model_copy(
            update={
                "status": status,
                "sent_at": sent_at,
                "provider_message_id": provider_message_id,
            }
        )
        return self.message

    async def count_sent_since(self, campaign_id: UUID, since: datetime) -> int:
        return self.sent_count


class FakeCampaignRepository:
    def __init__(self, campaign: Campaign) -> None:
        self.campaign = campaign

    async def add(self, **kwargs: Any) -> Campaign:
        raise NotImplementedError

    async def get(self, campaign_id: UUID) -> Campaign | None:
        return self.campaign if campaign_id == self.campaign.id else None

    async def list_all(self) -> list[Campaign]:
        raise NotImplementedError

    async def update_status(self, campaign_id: UUID, status: object, *, at: datetime) -> Campaign:
        raise NotImplementedError


class FakeLeadRepository:
    def __init__(self, lead: Lead) -> None:
        self.lead = lead
        self.status_updates: list[LeadStatus] = []

    async def get(self, lead_id: UUID) -> Lead | None:
        return self.lead if lead_id == self.lead.id else None

    async def update_status(self, lead_id: UUID, status: LeadStatus, *, at: datetime) -> Lead:
        self.status_updates.append(status)
        self.lead = self.lead.with_status(status, at=at)
        return self.lead


class FakePersonRepository:
    def __init__(self, person: Person) -> None:
        self.person = person

    async def add(self, **kwargs: Any) -> Person:
        raise NotImplementedError

    async def get(self, person_id: UUID) -> Person | None:
        return self.person if person_id == self.person.id else None

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


class FakeEvidenceRepository:
    def __init__(self, evidence: list[Evidence]) -> None:
        self._by_id = {e.id: e for e in evidence}

    async def add(self, **kwargs: Any) -> Evidence:
        raise NotImplementedError

    async def get(self, evidence_id: UUID) -> Evidence | None:
        return self._by_id.get(evidence_id)

    async def list_by_entity(self, entity_type: str, entity_id: UUID) -> list[Evidence]:
        raise NotImplementedError


class FakeSuppressionRepository:
    def __init__(self, suppressed: set[str] | None = None) -> None:
        self._suppressed = suppressed or set()

    async def add(self, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def is_suppressed(self, identifier_type: str, identifier: str) -> bool:
        return identifier in self._suppressed

    async def get(self, suppression_entry_id: UUID) -> Any:
        raise NotImplementedError


class FakeApprovalRepository:
    def __init__(self, approval: Approval | None = None) -> None:
        self.approval = approval

    async def add(self, **kwargs: Any) -> Approval:
        raise NotImplementedError

    async def get(self, approval_id: UUID) -> Approval | None:
        raise NotImplementedError

    async def get_latest_for_entity(self, entity_type: str, entity_id: UUID) -> Approval | None:
        return self.approval

    async def decide(self, approval_id: UUID, **kwargs: Any) -> Approval:
        raise NotImplementedError


class FakeMessageSender:
    def __init__(self) -> None:
        self.sent: list[Message] = []

    async def send(self, message: Message) -> str:
        self.sent.append(message)
        return "provider-msg-id-123"


class FakeAuditLogRepository:
    def __init__(self) -> None:
        self.recorded: list[AuditLog] = []

    async def record(self, **kwargs: Any) -> AuditLog:
        log = AuditLog(id=uuid4(), organization_id=uuid4(), created_at=NOW, **kwargs)
        self.recorded.append(log)
        return log


def _lead(organization_id: UUID, *, status: LeadStatus = LeadStatus.READY) -> Lead:
    return Lead(
        id=uuid4(),
        organization_id=organization_id,
        company_id=uuid4(),
        person_id=uuid4(),
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


def _person(person_id: UUID, *, email: str | None = "prospect@example.com") -> Person:
    return Person(
        id=person_id,
        organization_id=uuid4(),
        company_id=uuid4(),
        full_name="Jane Doe",
        email=email,
        email_status=EmailStatus.VALID if email else None,
        created_at=NOW,
        updated_at=NOW,
    )


def _campaign(organization_id: UUID, **overrides: Any) -> Campaign:
    base: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": organization_id,
        "name": "Q4 outbound",
        "status": CampaignStatus.ACTIVE,
        "channels": ["email"],
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return Campaign(**base)


def _message(lead_id: UUID, campaign_id: UUID, **overrides: Any) -> Message:
    base: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "campaign_id": campaign_id,
        "lead_id": lead_id,
        "channel": "email",
        "body": "Congrats on the raise.",
        "status": "DRAFT",
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return Message(**base)


def _harness(
    *,
    campaign: Campaign,
    lead: Lead,
    person: Person,
    message: Message,
    suppressed: set[str] | None = None,
    approval: Approval | None = None,
) -> tuple[SendMessage, FakeMessageRepository, FakeMessageSender, FakeLeadRepository]:
    messages = FakeMessageRepository(message)
    sender = FakeMessageSender()
    leads = FakeLeadRepository(lead)
    send_message = SendMessage(
        messages,
        FakeCampaignRepository(campaign),
        leads,
        FakePersonRepository(person),
        FakeEvidenceRepository([]),
        FakeSuppressionRepository(suppressed),
        FakeApprovalRepository(approval),
        sender,
        FakeAuditLogRepository(),
    )
    return send_message, messages, sender, leads


@pytest.mark.asyncio
async def test_a_fully_satisfied_send_calls_the_sender_and_persists_the_result() -> None:
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id)
    campaign = _campaign(org_id)
    message = _message(lead.id, campaign.id)
    approval = Approval(
        id=uuid4(),
        organization_id=org_id,
        entity_type="Message",
        entity_id=message.id,
        action_type="MESSAGE_SEND",
        status=ApprovalStatus.APPROVED,
        created_at=NOW,
    )
    send_message, _messages, sender, leads = _harness(
        campaign=campaign, lead=lead, person=person, message=message, approval=approval
    )

    updated = await send_message(message.id, now=NOW, auto_approval_enabled=False)

    assert len(sender.sent) == 1
    assert updated.status == "SENT"
    assert updated.provider_message_id == "provider-msg-id-123"
    assert leads.status_updates == [LeadStatus.CONTACTED]


@pytest.mark.asyncio
async def test_a_suppressed_target_is_denied_and_the_sender_is_never_called() -> None:
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id, email="suppressed@example.com")
    campaign = _campaign(org_id)
    message = _message(lead.id, campaign.id)
    approval = Approval(
        id=uuid4(),
        organization_id=org_id,
        entity_type="Message",
        entity_id=message.id,
        action_type="MESSAGE_SEND",
        status=ApprovalStatus.APPROVED,
        created_at=NOW,
    )
    send_message, messages, sender, _leads = _harness(
        campaign=campaign,
        lead=lead,
        person=person,
        message=message,
        suppressed={"suppressed@example.com"},
        approval=approval,
    )

    with pytest.raises(PolicyDeniedError) as excinfo:
        await send_message(message.id, now=NOW, auto_approval_enabled=False)

    assert "is_suppressed" in excinfo.value.failed_checks
    assert sender.sent == []
    assert messages.message.status == "DRAFT"


@pytest.mark.asyncio
async def test_a_paused_campaign_is_denied_and_the_sender_is_never_called() -> None:
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id)
    campaign = _campaign(org_id, status=CampaignStatus.PAUSED)
    message = _message(lead.id, campaign.id)
    approval = Approval(
        id=uuid4(),
        organization_id=org_id,
        entity_type="Message",
        entity_id=message.id,
        action_type="MESSAGE_SEND",
        status=ApprovalStatus.APPROVED,
        created_at=NOW,
    )
    send_message, _messages, sender, _leads = _harness(
        campaign=campaign, lead=lead, person=person, message=message, approval=approval
    )

    with pytest.raises(PolicyDeniedError) as excinfo:
        await send_message(message.id, now=NOW, auto_approval_enabled=False)

    assert "campaign_active" in excinfo.value.failed_checks
    assert sender.sent == []


@pytest.mark.asyncio
async def test_a_channel_the_campaign_does_not_allow_is_denied() -> None:
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id)
    campaign = _campaign(org_id, channels=["linkedin"])
    message = _message(lead.id, campaign.id)
    approval = Approval(
        id=uuid4(),
        organization_id=org_id,
        entity_type="Message",
        entity_id=message.id,
        action_type="MESSAGE_SEND",
        status=ApprovalStatus.APPROVED,
        created_at=NOW,
    )
    send_message, _messages, sender, _leads = _harness(
        campaign=campaign, lead=lead, person=person, message=message, approval=approval
    )

    with pytest.raises(PolicyDeniedError) as excinfo:
        await send_message(message.id, now=NOW, auto_approval_enabled=False)

    assert "channel_allowed" in excinfo.value.failed_checks
    assert sender.sent == []


@pytest.mark.asyncio
async def test_exceeding_the_daily_rate_limit_is_denied() -> None:
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id)
    campaign = _campaign(org_id, limits={"max_sends_per_day": 1})
    message = _message(lead.id, campaign.id)
    approval = Approval(
        id=uuid4(),
        organization_id=org_id,
        entity_type="Message",
        entity_id=message.id,
        action_type="MESSAGE_SEND",
        status=ApprovalStatus.APPROVED,
        created_at=NOW,
    )
    send_message, messages, sender, _leads = _harness(
        campaign=campaign, lead=lead, person=person, message=message, approval=approval
    )
    messages.sent_count = 1

    with pytest.raises(PolicyDeniedError) as excinfo:
        await send_message(message.id, now=NOW, auto_approval_enabled=False)

    assert "rate_limit_ok" in excinfo.value.failed_checks
    assert sender.sent == []


@pytest.mark.asyncio
async def test_missing_evidence_denies_the_send() -> None:
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id)
    campaign = _campaign(org_id)
    message = _message(lead.id, campaign.id, evidence_ids=[uuid4()])
    approval = Approval(
        id=uuid4(),
        organization_id=org_id,
        entity_type="Message",
        entity_id=message.id,
        action_type="MESSAGE_SEND",
        status=ApprovalStatus.APPROVED,
        created_at=NOW,
    )
    send_message, _messages, sender, _leads = _harness(
        campaign=campaign, lead=lead, person=person, message=message, approval=approval
    )

    with pytest.raises(PolicyDeniedError) as excinfo:
        await send_message(message.id, now=NOW, auto_approval_enabled=False)

    assert "evidence_valid" in excinfo.value.failed_checks
    assert sender.sent == []


@pytest.mark.asyncio
async def test_an_already_sent_message_cannot_be_sent_again() -> None:
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id)
    campaign = _campaign(org_id)
    message = _message(lead.id, campaign.id, status="SENT")
    approval = Approval(
        id=uuid4(),
        organization_id=org_id,
        entity_type="Message",
        entity_id=message.id,
        action_type="MESSAGE_SEND",
        status=ApprovalStatus.APPROVED,
        created_at=NOW,
    )
    send_message, _messages, sender, _leads = _harness(
        campaign=campaign, lead=lead, person=person, message=message, approval=approval
    )

    with pytest.raises(PolicyDeniedError) as excinfo:
        await send_message(message.id, now=NOW, auto_approval_enabled=False)

    assert "no_duplicate_send" in excinfo.value.failed_checks
    assert sender.sent == []


@pytest.mark.asyncio
async def test_a_message_with_no_approval_decision_requires_approval_and_is_not_sent() -> None:
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id)
    campaign = _campaign(org_id)
    message = _message(lead.id, campaign.id)
    send_message, _messages, sender, _leads = _harness(
        campaign=campaign, lead=lead, person=person, message=message, approval=None
    )

    with pytest.raises(PolicyDeniedError) as excinfo:
        await send_message(message.id, now=NOW, auto_approval_enabled=False)

    assert excinfo.value.decision == "REQUIRE_APPROVAL"
    assert sender.sent == []


@pytest.mark.asyncio
async def test_auto_approval_lets_an_auto_policy_campaign_send_with_no_decided_approval() -> None:
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id)
    campaign = _campaign(org_id, approval_policy={"mode": "auto"})
    message = _message(lead.id, campaign.id)
    send_message, _messages, sender, _leads = _harness(
        campaign=campaign, lead=lead, person=person, message=message, approval=None
    )

    await send_message(message.id, now=NOW, auto_approval_enabled=True)

    assert len(sender.sent) == 1


@pytest.mark.asyncio
async def test_auto_approval_flag_off_still_requires_a_human_decision() -> None:
    """The feature flag (§51) gates whether an `approval_policy: {mode: auto}` campaign is
    even allowed to skip human approval — a campaign cannot opt itself out of §51's own
    default-off rule."""
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id)
    campaign = _campaign(org_id, approval_policy={"mode": "auto"})
    message = _message(lead.id, campaign.id)
    send_message, _messages, sender, _leads = _harness(
        campaign=campaign, lead=lead, person=person, message=message, approval=None
    )

    with pytest.raises(PolicyDeniedError):
        await send_message(message.id, now=NOW, auto_approval_enabled=False)

    assert sender.sent == []


@pytest.mark.asyncio
async def test_sending_an_unknown_message_raises_not_found() -> None:
    org_id = uuid4()
    lead = _lead(org_id)
    person = _person(lead.person_id)
    campaign = _campaign(org_id)
    message = _message(lead.id, campaign.id)
    send_message, _messages, sender, _leads = _harness(
        campaign=campaign, lead=lead, person=person, message=message
    )

    with pytest.raises(NotFoundError):
        await send_message(uuid4(), now=NOW, auto_approval_enabled=False)

    assert sender.sent == []
