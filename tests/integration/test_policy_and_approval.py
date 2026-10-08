"""Milestone 16's acceptance criterion, proven literally: "A policy violation cannot result in
an external message send" (CLAUDE.md §68).

No Anthropic call exists anywhere in this milestone — there is nothing to mock. Everything here
is real: real Postgres, real RLS (`SqlAlchemyApprovalRepository.create`/
`SqlAlchemySuppressionRepository`/`SqlAlchemyMessageRepository`), and the real
`DecideMessageApproval`/`AddSuppressionEntry`/`SendMessage`/`evaluate_outbound_send` path. The
one substitution is `MessageSender` itself —
Milestone 17's email subsystem is the first real channel provider; a `FakeMessageSender` that
records every call it receives is exactly what proves "never calls the sender" on a denied path,
the same way Milestone 09's tests prove a tool was or was not invoked.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from colt_application import RecordEvidence
from colt_application.errors import PolicyDeniedError
from colt_application.use_cases.add_suppression_entry import AddSuppressionEntry
from colt_application.use_cases.create_campaign import CreateCampaign
from colt_application.use_cases.decide_message_approval import DecideMessageApproval
from colt_application.use_cases.draft_message import DraftMessage
from colt_application.use_cases.send_message import SendMessage
from colt_application.use_cases.validate_campaign import ValidateCampaign
from colt_db.models.audit_log import AuditLogModel
from colt_db.repositories.approval_repository import SqlAlchemyApprovalRepository
from colt_db.repositories.audit_log_repository import SqlAlchemyAuditLogRepository
from colt_db.repositories.campaign_repository import SqlAlchemyCampaignRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.message_repository import SqlAlchemyMessageRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_db.repositories.suppression_repository import SqlAlchemySuppressionRepository
from colt_domain import LeadStatus, Message, Person, SuppressionReason

SessionFactory = Any
NOW = datetime.now(UTC)


class FakeMessageSender:
    """`Milestone 17`'s real email adapter does not exist yet — see this module's own docstring."""

    def __init__(self) -> None:
        self.sent: list[Message] = []

    async def send(self, message: Message, *, recipient: Person) -> str:
        self.sent.append(message)
        return "provider-msg-id-integration-test"


async def _seed_user(session: Any, org_id: UUID) -> UUID:
    """`Approval.approved_by` has a real foreign key to `users.id` — a human decision needs a
    real reviewer row, the same way `two_organizations` seeds real organizations directly
    rather than through a use case that doesn't exist for this (users are provisioned through
    the auth flow, not an application-layer `CreateUser`)."""
    user_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO users (id, organization_id, external_auth_id, email, name, role) "
            "VALUES (:id, :org_id, :auth_id, :email, 'Reviewer', 'MANAGER')"
        ),
        {
            "id": user_id,
            "org_id": org_id,
            "auth_id": f"kc-sub-{user_id}",
            "email": f"reviewer-{user_id}@example.com",
        },
    )
    return user_id


async def _seed_ready_message(
    session: Any, org_id: UUID, *, email: str, limits: dict[str, Any] | None = None
) -> tuple[UUID, UUID]:
    """Company -> Person -> Lead (READY) -> validated ACTIVE Campaign -> drafted Message.
    Returns (lead_id, message_id)."""
    companies = await SqlAlchemyCompanyRepository.create(session, org_id)
    company = await companies.add(name="Acme Rockets")
    persons = SqlAlchemyPersonRepository(session, org_id)
    person = await persons.add(company_id=company.id, full_name="Jane Doe", email=email)
    leads = SqlAlchemyLeadRepository(session, org_id)
    lead = await leads.add(company_id=company.id, person_id=person.id)
    lead = await leads.update_status(lead.id, LeadStatus.PENDING_APPROVAL, at=NOW)

    campaigns = await SqlAlchemyCampaignRepository.create(session, org_id)
    campaign = await CreateCampaign(campaigns)(
        name="Q4 outbound",
        icp_definition={"industry": "SaaS"},
        channels=["email"],
        schedule={"timezone": "UTC"},
        limits=limits or {"max_sends_per_day": 50},
    )
    audit_logs = SqlAlchemyAuditLogRepository(session, org_id)
    campaign = await ValidateCampaign(campaigns, audit_logs)(campaign.id, actor_id=uuid4(), now=NOW)
    assert campaign.status.value == "ACTIVE"

    evidence_repo = await SqlAlchemyEvidenceRepository.create(session, org_id)
    evidence = await RecordEvidence(evidence_repo)(
        entity_type="Company",
        entity_id=company.id,
        claim="Acme Rockets raised a $20M Series B.",
        source_url="https://example.com/news",
        observed_at=NOW,
    )

    messages = SqlAlchemyMessageRepository(session, org_id)
    message = await DraftMessage(messages, evidence_repo)(
        campaign_id=campaign.id,
        lead_id=lead.id,
        channel="email",
        body="Congrats on the raise - curious how you're scaling the team.",
        evidence_ids=[evidence.id],
    )
    return lead.id, message.id


@pytest.mark.asyncio
async def test_an_approved_message_within_policy_is_sent_and_persisted_through_real_postgres(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    session = await open_app_session()
    async with session, session.begin():
        lead_id, message_id = await _seed_ready_message(session, org_a, email="prospect@a.example")
        reviewer_id = await _seed_user(session, org_a)
        approvals = await SqlAlchemyApprovalRepository.create(session, org_a)
        leads = SqlAlchemyLeadRepository(session, org_a)
        audit_logs = await SqlAlchemyAuditLogRepository.create(session, org_a)
        messages = SqlAlchemyMessageRepository(session, org_a)
        decided = await DecideMessageApproval(messages, approvals, leads, audit_logs)(
            message_id, approve=True, decided_by=reviewer_id, reason="looks good", now=NOW
        )
        assert decided.approval_status == "APPROVED"

        sender = FakeMessageSender()
        campaigns = await SqlAlchemyCampaignRepository.create(session, org_a)
        persons = SqlAlchemyPersonRepository(session, org_a)
        evidence_repo = await SqlAlchemyEvidenceRepository.create(session, org_a)
        suppressions = await SqlAlchemySuppressionRepository.create(session, org_a)
        send_message = SendMessage(
            messages,
            campaigns,
            leads,
            persons,
            evidence_repo,
            suppressions,
            approvals,
            sender,
            audit_logs,
        )
        sent = await send_message(message_id, now=NOW, auto_approval_enabled=False)

    assert len(sender.sent) == 1
    assert sent.status == "SENT"
    assert sent.provider_message_id == "provider-msg-id-integration-test"

    # Independently re-read everything back from Postgres through a fresh session — not
    # trusting the previous call's in-memory return value.
    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        messages_verify = await SqlAlchemyMessageRepository.create(verify_session, org_a)
        reread = await messages_verify.get(message_id)
        assert reread is not None
        assert reread.status == "SENT"
        assert reread.provider_message_id == "provider-msg-id-integration-test"

        leads_verify = SqlAlchemyLeadRepository(verify_session, org_a)
        lead_reread = await leads_verify.get(lead_id)
        assert lead_reread is not None
        assert lead_reread.status == LeadStatus.CONTACTED

        audit_rows = (
            (
                await verify_session.execute(
                    select(AuditLogModel).where(AuditLogModel.entity_id == message_id)
                )
            )
            .scalars()
            .all()
        )
        actions = {row.action for row in audit_rows}
        assert "message_approval_decided" in actions
        assert "message_sent" in actions


@pytest.mark.asyncio
async def test_sending_without_an_approval_decision_is_denied_and_the_sender_is_never_called(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    session = await open_app_session()
    async with session, session.begin():
        _lead_id, message_id = await _seed_ready_message(
            session, org_a, email="prospect2@a.example"
        )
        messages = SqlAlchemyMessageRepository(session, org_a)
        campaigns = await SqlAlchemyCampaignRepository.create(session, org_a)
        leads = SqlAlchemyLeadRepository(session, org_a)
        persons = SqlAlchemyPersonRepository(session, org_a)
        evidence_repo = await SqlAlchemyEvidenceRepository.create(session, org_a)
        suppressions = await SqlAlchemySuppressionRepository.create(session, org_a)
        approvals = await SqlAlchemyApprovalRepository.create(session, org_a)
        audit_logs = await SqlAlchemyAuditLogRepository.create(session, org_a)
        sender = FakeMessageSender()
        send_message = SendMessage(
            messages,
            campaigns,
            leads,
            persons,
            evidence_repo,
            suppressions,
            approvals,
            sender,
            audit_logs,
        )

        with pytest.raises(PolicyDeniedError) as excinfo:
            await send_message(message_id, now=NOW, auto_approval_enabled=False)

    assert excinfo.value.decision == "REQUIRE_APPROVAL"
    assert sender.sent == []


@pytest.mark.asyncio
async def test_a_suppressed_target_blocks_the_send_even_once_approved(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations
    suppressed_email = "bounced@a.example"

    session = await open_app_session()
    async with session, session.begin():
        lead_id, message_id = await _seed_ready_message(session, org_a, email=suppressed_email)

        suppressions = await SqlAlchemySuppressionRepository.create(session, org_a)
        audit_logs = await SqlAlchemyAuditLogRepository.create(session, org_a)
        await AddSuppressionEntry(suppressions, audit_logs)(
            identifier_type="email",
            identifier=suppressed_email,
            reason=SuppressionReason.BOUNCE,
            source="email-provider-webhook",
        )

        reviewer_id = await _seed_user(session, org_a)
        approvals = await SqlAlchemyApprovalRepository.create(session, org_a)
        leads = SqlAlchemyLeadRepository(session, org_a)
        messages = SqlAlchemyMessageRepository(session, org_a)
        await DecideMessageApproval(messages, approvals, leads, audit_logs)(
            message_id, approve=True, decided_by=reviewer_id, reason=None, now=NOW
        )

        campaigns = await SqlAlchemyCampaignRepository.create(session, org_a)
        persons = SqlAlchemyPersonRepository(session, org_a)
        evidence_repo = await SqlAlchemyEvidenceRepository.create(session, org_a)
        sender = FakeMessageSender()
        send_message = SendMessage(
            messages,
            campaigns,
            leads,
            persons,
            evidence_repo,
            suppressions,
            approvals,
            sender,
            audit_logs,
        )

        with pytest.raises(PolicyDeniedError) as excinfo:
            await send_message(message_id, now=NOW, auto_approval_enabled=False)

    assert "is_suppressed" in excinfo.value.failed_checks
    assert sender.sent == []

    # Independently re-read: the message was never marked SENT.
    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        messages_verify = await SqlAlchemyMessageRepository.create(verify_session, org_a)
        reread = await messages_verify.get(message_id)
        assert reread is not None
        assert reread.status == "DRAFT"
        _ = lead_id


@pytest.mark.asyncio
async def test_a_suppression_entry_in_one_organization_does_not_suppress_another(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    """§18.1's "no campaign or agent may override a suppression entry" is organization-scoped
    by default (§10.18's own `organization_id` field) — only a system-wide entry (`organization_
    scoped=False`) is meant to cross tenants, proving the RLS departure in this milestone's own
    migration does not accidentally leak suppression across organizations."""
    org_a, org_b = two_organizations
    shared_email = "same-address@example.com"

    session_a = await open_app_session()
    async with session_a, session_a.begin():
        suppressions_a = await SqlAlchemySuppressionRepository.create(session_a, org_a)
        audit_logs_a = await SqlAlchemyAuditLogRepository.create(session_a, org_a)
        await AddSuppressionEntry(suppressions_a, audit_logs_a)(
            identifier_type="email",
            identifier=shared_email,
            reason=SuppressionReason.UNSUBSCRIBE,
            source="unsubscribe-link",
        )

    session_b = await open_app_session()
    async with session_b, session_b.begin():
        suppressions_b = await SqlAlchemySuppressionRepository.create(session_b, org_b)
        is_suppressed_in_b = await suppressions_b.is_suppressed("email", shared_email)

    assert is_suppressed_in_b is False
