"""`DecideMessageApproval` (CLAUDE.md §10.17, §26.2, Milestone 16)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application.errors import InvalidApprovalTransitionError, NotFoundError
from colt_application.use_cases.decide_message_approval import DecideMessageApproval
from colt_domain import Approval, ApprovalStatus, AuditLog, Lead, LeadStatus, Message

NOW = datetime.now(UTC)


class FakeMessageRepository:
    def __init__(self, message: Message) -> None:
        self.message = message

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
        self.message = self.message.model_copy(update={"approval_status": approval_status})
        return self.message

    async def update_send_result(
        self, message_id: UUID, *, status: str, sent_at: datetime, provider_message_id: str | None
    ) -> Message:
        raise NotImplementedError

    async def count_sent_since(self, campaign_id: UUID, since: datetime) -> int:
        raise NotImplementedError


class FakeApprovalRepository:
    def __init__(self, approval: Approval | None = None) -> None:
        self.by_id: dict[UUID, Approval] = {approval.id: approval} if approval else {}
        self.decisions: list[ApprovalStatus] = []

    async def add(self, **kwargs: Any) -> Approval:
        approval = Approval(id=uuid4(), organization_id=uuid4(), created_at=NOW, **kwargs)
        self.by_id[approval.id] = approval
        return approval

    async def get(self, approval_id: UUID) -> Approval | None:
        return self.by_id.get(approval_id)

    async def get_latest_for_entity(self, entity_type: str, entity_id: UUID) -> Approval | None:
        matches = [
            a
            for a in self.by_id.values()
            if a.entity_type == entity_type and a.entity_id == entity_id
        ]
        return max(matches, key=lambda a: a.created_at) if matches else None

    async def decide(
        self,
        approval_id: UUID,
        *,
        status: ApprovalStatus,
        approved_by: UUID,
        reason: str | None,
        decided_at: datetime,
    ) -> Approval:
        self.decisions.append(status)
        updated = self.by_id[approval_id].model_copy(
            update={
                "status": status,
                "approved_by": approved_by,
                "reason": reason,
                "decided_at": decided_at,
            }
        )
        self.by_id[approval_id] = updated
        return updated


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


class FakeAuditLogRepository:
    def __init__(self) -> None:
        self.recorded: list[AuditLog] = []

    async def record(self, **kwargs: Any) -> AuditLog:
        log = AuditLog(id=uuid4(), organization_id=uuid4(), created_at=NOW, **kwargs)
        self.recorded.append(log)
        return log


def _lead(status: LeadStatus = LeadStatus.PENDING_APPROVAL) -> Lead:
    return Lead(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        person_id=uuid4(),
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


def _message(lead_id: UUID) -> Message:
    return Message(
        id=uuid4(),
        organization_id=uuid4(),
        campaign_id=uuid4(),
        lead_id=lead_id,
        channel="email",
        body="Hello there.",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_approving_a_message_with_no_prior_approval_request_creates_and_decides_one() -> None:
    lead = _lead()
    message = _message(lead.id)
    messages = FakeMessageRepository(message)
    approvals = FakeApprovalRepository()
    leads = FakeLeadRepository(lead)
    audit_logs = FakeAuditLogRepository()
    decide = DecideMessageApproval(messages, approvals, leads, audit_logs)

    updated = await decide(
        message.id, approve=True, decided_by=uuid4(), reason="looks good", now=NOW
    )

    assert updated.approval_status == ApprovalStatus.APPROVED.value
    assert approvals.decisions == [ApprovalStatus.APPROVED]
    assert leads.status_updates == [LeadStatus.READY]
    (log,) = audit_logs.recorded
    assert log.action == "message_approval_decided"


@pytest.mark.asyncio
async def test_rejecting_a_message_does_not_move_the_lead_forward() -> None:
    lead = _lead()
    message = _message(lead.id)
    messages = FakeMessageRepository(message)
    approvals = FakeApprovalRepository()
    leads = FakeLeadRepository(lead)
    audit_logs = FakeAuditLogRepository()
    decide = DecideMessageApproval(messages, approvals, leads, audit_logs)

    updated = await decide(message.id, approve=False, decided_by=uuid4(), reason=None, now=NOW)

    assert updated.approval_status == ApprovalStatus.REJECTED.value
    assert leads.status_updates == []


@pytest.mark.asyncio
async def test_deciding_an_already_decided_approval_is_rejected() -> None:
    lead = _lead()
    message = _message(lead.id)
    messages = FakeMessageRepository(message)
    decided = Approval(
        id=uuid4(),
        organization_id=uuid4(),
        entity_type="Message",
        entity_id=message.id,
        action_type="MESSAGE_SEND",
        status=ApprovalStatus.APPROVED,
        created_at=NOW,
    )
    approvals = FakeApprovalRepository(decided)
    leads = FakeLeadRepository(lead)
    audit_logs = FakeAuditLogRepository()
    decide = DecideMessageApproval(messages, approvals, leads, audit_logs)

    with pytest.raises(InvalidApprovalTransitionError):
        await decide(message.id, approve=True, decided_by=uuid4(), reason=None, now=NOW)


@pytest.mark.asyncio
async def test_deciding_an_unknown_message_raises_not_found() -> None:
    lead = _lead()
    message = _message(lead.id)
    messages = FakeMessageRepository(message)
    approvals = FakeApprovalRepository()
    leads = FakeLeadRepository(lead)
    audit_logs = FakeAuditLogRepository()
    decide = DecideMessageApproval(messages, approvals, leads, audit_logs)

    with pytest.raises(NotFoundError):
        await decide(uuid4(), approve=True, decided_by=uuid4(), reason=None, now=NOW)
