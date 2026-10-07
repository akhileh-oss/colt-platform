"""Milestone 17's acceptance criterion, proven literally: "Local full outbound lifecycle works
without touching the public internet" (CLAUDE.md §68, §29).

Every step is real: real Postgres (draft -> approve -> send, through the same `SendMessage` path
Milestone 16 built), real SMTP to a local Mailpit instance (`SmtpEmailProvider`,
`EmailMessageSender`), a real read-back through Mailpit's own REST API (`MailpitInboxClient`),
a real simulated reply sent back into Mailpit (exploiting Mailpit's catch-all nature — it accepts
mail to any address), and `ProcessInboundEmail` threading that reply onto a real `Conversation`/
`ConversationEvent` row. Nothing here leaves localhost: Mailpit's SMTP/API ports and Postgres are
both `docker compose` services bound to `localhost`.

Requires a real Postgres (`make dev` + `make migrate`) and a real local Mailpit
(`docker compose up -d mailpit`). Marked `integration`.
"""

from __future__ import annotations

import smtplib
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select

from colt_application import RecordEvidence
from colt_application.use_cases.create_campaign import CreateCampaign
from colt_application.use_cases.decide_message_approval import DecideMessageApproval
from colt_application.use_cases.draft_message import DraftMessage
from colt_application.use_cases.process_inbound_email import ProcessInboundEmail
from colt_application.use_cases.send_message import SendMessage
from colt_application.use_cases.validate_campaign import ValidateCampaign
from colt_config import EmailSettings
from colt_db.models.conversation_event import ConversationEventModel
from colt_db.repositories.approval_repository import SqlAlchemyApprovalRepository
from colt_db.repositories.audit_log_repository import SqlAlchemyAuditLogRepository
from colt_db.repositories.campaign_repository import SqlAlchemyCampaignRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.conversation_event_repository import (
    SqlAlchemyConversationEventRepository,
)
from colt_db.repositories.conversation_repository import SqlAlchemyConversationRepository
from colt_db.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.message_repository import SqlAlchemyMessageRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_db.repositories.suppression_repository import SqlAlchemySuppressionRepository
from colt_domain import LeadStatus
from colt_integrations.email.inbox import MailpitInboxClient
from colt_integrations.email.message_sender import EmailMessageSender
from colt_integrations.email.smtp import SmtpEmailProvider

SessionFactory = Any
NOW = datetime.now(UTC)
_EMAIL_SETTINGS = EmailSettings()


async def _seed_user(session: Any, org_id: UUID) -> UUID:
    from sqlalchemy import text

    user_id = uuid.uuid4()
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


async def _send_simulated_reply(*, to_address: str, from_address: str, in_reply_to: str) -> str:
    """A lead's reply, sent straight into the same local Mailpit the outbound send used —
    Mailpit is a catch-all, so this does not need `to_address` to be a real mailbox either."""
    message = EmailMessage()
    reply_message_id = make_msgid(domain="example.com")
    message["Message-ID"] = reply_message_id
    message["From"] = from_address
    message["To"] = to_address
    message["Subject"] = f"Re: integration test {uuid.uuid4()}"
    message["In-Reply-To"] = in_reply_to
    message.set_content("Sounds interesting, tell me more.")

    with smtplib.SMTP(_EMAIL_SETTINGS.smtp_host, _EMAIL_SETTINGS.smtp_port, timeout=10) as client:
        client.send_message(message)
    return reply_message_id


@pytest.mark.asyncio
async def test_draft_approve_send_and_inbound_reply_round_trip_through_real_mailpit(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations
    lead_email = f"prospect-{uuid.uuid4()}@example.com"

    session = await open_app_session()
    async with session, session.begin():
        companies = await SqlAlchemyCompanyRepository.create(session, org_a)
        company = await companies.add(name="Acme Rockets")
        persons = SqlAlchemyPersonRepository(session, org_a)
        person = await persons.add(company_id=company.id, full_name="Jane Doe", email=lead_email)
        leads = SqlAlchemyLeadRepository(session, org_a)
        lead = await leads.add(company_id=company.id, person_id=person.id)
        lead = await leads.update_status(lead.id, LeadStatus.PENDING_APPROVAL, at=NOW)

        campaigns = await SqlAlchemyCampaignRepository.create(session, org_a)
        campaign = await CreateCampaign(campaigns)(
            name="Q4 outbound",
            icp_definition={"industry": "SaaS"},
            channels=["email"],
            schedule={"timezone": "UTC"},
            limits={"max_sends_per_day": 50},
        )
        audit_logs = SqlAlchemyAuditLogRepository(session, org_a)
        campaign = await ValidateCampaign(campaigns, audit_logs)(
            campaign.id, actor_id=uuid.uuid4(), now=NOW
        )

        evidence_repo = await SqlAlchemyEvidenceRepository.create(session, org_a)
        evidence = await RecordEvidence(evidence_repo)(
            entity_type="Company",
            entity_id=company.id,
            claim="Acme Rockets raised a $20M Series B.",
            source_url="https://example.com/news",
            observed_at=NOW,
        )

        messages = SqlAlchemyMessageRepository(session, org_a)
        message = await DraftMessage(messages, evidence_repo)(
            campaign_id=campaign.id,
            lead_id=lead.id,
            channel="email",
            body="Congrats on the raise - curious how you're scaling the team.",
            evidence_ids=[evidence.id],
        )

        reviewer_id = await _seed_user(session, org_a)
        approvals = await SqlAlchemyApprovalRepository.create(session, org_a)
        audit_logs = await SqlAlchemyAuditLogRepository.create(session, org_a)
        await DecideMessageApproval(messages, approvals, leads, audit_logs)(
            message.id, approve=True, decided_by=reviewer_id, reason="looks good", now=NOW
        )

        suppressions = await SqlAlchemySuppressionRepository.create(session, org_a)
        provider = SmtpEmailProvider(_EMAIL_SETTINGS)
        sender = EmailMessageSender(
            provider, messages, unsubscribe_url_base="http://localhost:8000/unsubscribe"
        )
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
        sent = await send_message(message.id, now=NOW, auto_approval_enabled=False)

    assert sent.status == "SENT"
    assert sent.provider_message_id is not None
    outbound_provider_message_id = sent.provider_message_id

    # --- Real read-back through Mailpit's own REST API -------------------------------------
    inbox = MailpitInboxClient(_EMAIL_SETTINGS)
    outbound_ids = await inbox.list_messages(limit=20)
    outbound_mailpit_message = next(
        m
        for m in [await inbox.get_message(i) for i in outbound_ids]
        if m.message_id == outbound_provider_message_id.strip("<>")
    )
    assert outbound_mailpit_message.from_address == _EMAIL_SETTINGS.from_address
    assert outbound_mailpit_message.to_addresses == [lead_email]

    # --- A real simulated reply, sent back into the same local Mailpit ----------------------
    await _send_simulated_reply(
        to_address=_EMAIL_SETTINGS.from_address,
        from_address=lead_email,
        in_reply_to=outbound_provider_message_id,
    )

    reply_ids = await inbox.list_messages(limit=20)
    reply_message = next(
        m
        for m in [await inbox.get_message(i) for i in reply_ids]
        if m.in_reply_to == outbound_provider_message_id
    )

    # --- ProcessInboundEmail threads the reply onto a real Conversation/ConversationEvent ---
    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        messages_verify = SqlAlchemyMessageRepository(verify_session, org_a)
        conversations = SqlAlchemyConversationRepository(verify_session, org_a)
        conversation_events = await SqlAlchemyConversationEventRepository.create(
            verify_session, org_a
        )
        process_inbound = ProcessInboundEmail(messages_verify, conversations, conversation_events)
        event = await process_inbound(
            provider_message_id=reply_message.message_id or reply_message.id,
            in_reply_to=reply_message.in_reply_to or "",
            from_email=reply_message.from_address,
            subject=reply_message.subject,
            body=reply_message.text_body,
            received_at=NOW,
        )
        assert event.event_type == "message_received"

        conversation = await conversations.get_by_lead_and_channel(lead.id, "email")
        assert conversation is not None
        assert conversation.last_activity_at is not None

        rows = (
            (
                await verify_session.execute(
                    select(ConversationEventModel).where(
                        ConversationEventModel.conversation_id == conversation.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert any(row.event_type == "message_received" for row in rows)
