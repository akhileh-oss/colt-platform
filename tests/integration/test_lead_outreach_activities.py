"""Milestone 18's acceptance criterion, proven as far as this environment allows: "Workflow
survives restarts, does not duplicate sends, and reacts correctly to replies/unsubscribes"
(CLAUDE.md §68).

**What this proves for real, against real Postgres:**

- `load_outreach_state_activity`'s eligibility gating, "research if stale/missing" check, and
  next-sequence-step selection — called directly as a plain async function (a `@activity.defn`
  function is still an ordinary Python coroutine outside of Temporal's own activity execution
  context; neither this activity nor `check_conversation_activity` touches `activity.info()`, so
  this is a legitimate way to exercise their real logic against real data without a running
  worker). Each activity opens its own session via `get_default_engine()`, a separate connection
  from this test's own seeding session — so every test commits its seed data first, then calls
  the activity in a second, independent transaction, the same two-session shape
  `test_policy_and_approval.py` uses to prove persistence rather than in-memory state.
- `check_conversation_activity` correctly detecting a reply (`Conversation.last_activity_at`
  advancing past the send) and an unsubscription (`Lead.status`/a real suppression entry) — the
  literal "reacts correctly to replies/unsubscribes" criterion.
- "Does not duplicate sends" is `SendMessage`'s own cross-row idempotency check
  (`tests/integration/test_policy_and_approval.py`'s suppression test and the `colt-application`
  unit suite's idempotency tests already prove this against real Postgres) — `send_email_
  activity` (Milestone 17) composes that exact use case unchanged, so re-proving it here would
  only be testing Milestone 16/17's code a second time, not anything new this milestone adds.

**What this environment cannot prove, and why:**

`research_company_activity` and `draft_next_message_activity` each construct a real
`AnthropicGateway` from `AnthropicSettings` and call it for real — no real Anthropic API key
exists in this environment (the same caveat carried since Milestone 08), so no test here drives
either activity, or the full `LeadOutreachWorkflow` end to end, against a real model. "Workflow
survives restarts" specifically needs a real worker process killed and replaced
(`tests/integration/test_workflow_durability.py`'s own subprocess pattern) — but
`LeadOutreachWorkflow` cannot reach a durable wait state without first drafting a message, which
cannot happen here without a real Anthropic call. The underlying durability mechanism itself
(workflow state lives in the Temporal server, not worker process memory) is Milestone 06's own
literal proof, already covering every workflow this worker registers, `LeadOutreachWorkflow`
included — re-running that same SDK-level proof against this specific workflow would exercise
the Temporal SDK a second time, not any of this milestone's own code.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from colt_application import RecordEvidence
from colt_application.use_cases.add_sequence_step import AddSequenceStep
from colt_application.use_cases.add_suppression_entry import AddSuppressionEntry
from colt_application.use_cases.create_campaign import CreateCampaign
from colt_application.use_cases.draft_message import DraftMessage
from colt_application.use_cases.validate_campaign import ValidateCampaign
from colt_db.repositories.audit_log_repository import SqlAlchemyAuditLogRepository
from colt_db.repositories.campaign_repository import SqlAlchemyCampaignRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.conversation_repository import SqlAlchemyConversationRepository
from colt_db.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.message_repository import SqlAlchemyMessageRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_db.repositories.sequence_step_repository import SqlAlchemySequenceStepRepository
from colt_db.repositories.suppression_repository import SqlAlchemySuppressionRepository
from colt_domain import LeadStatus, SuppressionReason
from colt_workflows.activities.lead_outreach import (
    CheckConversationInput,
    LoadOutreachStateInput,
    check_conversation_activity,
    load_outreach_state_activity,
)

SessionFactory = Any
NOW = datetime.now(UTC)


async def _seed_lead_and_campaign(
    session: Any, org_id: UUID, *, email: str
) -> tuple[UUID, UUID, UUID]:
    """Company -> Person -> Lead (QUALIFIED) -> validated ACTIVE Campaign with one sequence
    step. Returns (lead_id, campaign_id, sequence_step_id)."""
    companies = await SqlAlchemyCompanyRepository.create(session, org_id)
    company = await companies.add(name="Acme Rockets", domain="acme.example")
    persons = SqlAlchemyPersonRepository(session, org_id)
    person = await persons.add(company_id=company.id, full_name="Jane Doe", email=email)
    leads = SqlAlchemyLeadRepository(session, org_id)
    lead = await leads.add(company_id=company.id, person_id=person.id)
    lead = await leads.update_status(lead.id, LeadStatus.QUALIFIED, at=NOW)

    campaigns = await SqlAlchemyCampaignRepository.create(session, org_id)
    campaign = await CreateCampaign(campaigns)(
        name="Q4 outbound",
        icp_definition={"industry": "SaaS"},
        channels=["email"],
        schedule={"timezone": "UTC"},
        limits={"max_sends_per_day": 50},
    )
    audit_logs = SqlAlchemyAuditLogRepository(session, org_id)
    campaign = await ValidateCampaign(campaigns, audit_logs)(campaign.id, actor_id=uuid4(), now=NOW)
    assert campaign.status.value == "ACTIVE"

    add_sequence_step = AddSequenceStep(
        campaigns, SqlAlchemySequenceStepRepository(session, org_id)
    )
    step = await add_sequence_step(
        campaign_id=campaign.id, step_order=1, channel="email", message_strategy="intro"
    )
    return lead.id, campaign.id, step.id


@pytest.mark.asyncio
async def test_a_newly_qualified_lead_with_no_evidence_needs_research_and_has_a_next_step(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        lead_id, campaign_id, step_id = await _seed_lead_and_campaign(
            seed_session, org_a, email="prospect@a.example"
        )

    state = await load_outreach_state_activity(
        LoadOutreachStateInput(
            organization_id=str(org_a), lead_id=str(lead_id), campaign_id=str(campaign_id)
        )
    )

    assert state.eligible
    assert state.needs_research
    assert state.next_sequence_step_id == str(step_id)
    assert not state.sequence_exhausted


@pytest.mark.asyncio
async def test_fresh_evidence_means_no_research_is_needed(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        lead_id, campaign_id, _step_id = await _seed_lead_and_campaign(
            seed_session, org_a, email="prospect2@a.example"
        )
        leads = SqlAlchemyLeadRepository(seed_session, org_a)
        lead = await leads.get(lead_id)
        assert lead is not None

        evidence_repo = await SqlAlchemyEvidenceRepository.create(seed_session, org_a)
        await RecordEvidence(evidence_repo)(
            entity_type="Company",
            entity_id=lead.company_id,
            claim="Acme Rockets raised a $20M Series B.",
            source_url="https://example.com/news",
            observed_at=NOW,
        )

    state = await load_outreach_state_activity(
        LoadOutreachStateInput(
            organization_id=str(org_a), lead_id=str(lead_id), campaign_id=str(campaign_id)
        )
    )

    assert not state.needs_research


@pytest.mark.asyncio
async def test_a_lead_already_sent_every_step_has_an_exhausted_sequence(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        lead_id, campaign_id, step_id = await _seed_lead_and_campaign(
            seed_session, org_a, email="prospect3@a.example"
        )
        leads = SqlAlchemyLeadRepository(seed_session, org_a)
        lead = await leads.get(lead_id)
        assert lead is not None
        evidence_repo = await SqlAlchemyEvidenceRepository.create(seed_session, org_a)
        evidence = await RecordEvidence(evidence_repo)(
            entity_type="Company",
            entity_id=lead.company_id,
            claim="Acme Rockets raised a $20M Series B.",
            source_url="https://example.com/news",
            observed_at=NOW,
        )
        messages = SqlAlchemyMessageRepository(seed_session, org_a)
        draft = await DraftMessage(messages, evidence_repo)(
            campaign_id=campaign_id,
            lead_id=lead_id,
            channel="email",
            body="Hi there.",
            evidence_ids=[evidence.id],
            sequence_step_id=step_id,
        )
        await messages.update_send_result(
            draft.id, status="SENT", sent_at=NOW, provider_message_id="<already-sent@colt.local>"
        )

    state = await load_outreach_state_activity(
        LoadOutreachStateInput(
            organization_id=str(org_a), lead_id=str(lead_id), campaign_id=str(campaign_id)
        )
    )

    assert state.sequence_exhausted
    assert state.next_sequence_step_id is None


@pytest.mark.asyncio
async def test_a_suppressed_or_unsubscribed_lead_is_not_eligible(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations
    suppressed_email = "bounced@a.example"

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        lead_id, campaign_id, _step_id = await _seed_lead_and_campaign(
            seed_session, org_a, email=suppressed_email
        )
        suppressions = await SqlAlchemySuppressionRepository.create(seed_session, org_a)
        audit_logs = await SqlAlchemyAuditLogRepository.create(seed_session, org_a)
        await AddSuppressionEntry(suppressions, audit_logs)(
            identifier_type="email",
            identifier=suppressed_email,
            reason=SuppressionReason.BOUNCE,
            source="email_bounce",
        )

    state = await load_outreach_state_activity(
        LoadOutreachStateInput(
            organization_id=str(org_a), lead_id=str(lead_id), campaign_id=str(campaign_id)
        )
    )

    assert not state.eligible
    assert state.ineligible_reason == "suppressed"


@pytest.mark.asyncio
async def test_check_conversation_detects_a_real_reply_after_the_send(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    sent_at = NOW
    async with seed_session, seed_session.begin():
        lead_id, _campaign_id, _step_id = await _seed_lead_and_campaign(
            seed_session, org_a, email="prospect4@a.example"
        )
        conversations = await SqlAlchemyConversationRepository.create(seed_session, org_a)
        conversation = await conversations.add(lead_id=lead_id, channel="email")
        await conversations.touch_last_activity(conversation.id, at=sent_at + timedelta(minutes=5))

    result = await check_conversation_activity(
        CheckConversationInput(
            organization_id=str(org_a), lead_id=str(lead_id), since=sent_at.isoformat()
        )
    )

    assert result.replied
    assert not result.unsubscribed


@pytest.mark.asyncio
async def test_check_conversation_detects_a_real_unsubscribe(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        lead_id, _campaign_id, _step_id = await _seed_lead_and_campaign(
            seed_session, org_a, email="prospect5@a.example"
        )
        leads = SqlAlchemyLeadRepository(seed_session, org_a)
        await leads.update_status(lead_id, LeadStatus.UNSUBSCRIBED, at=NOW)

    result = await check_conversation_activity(
        CheckConversationInput(
            organization_id=str(org_a), lead_id=str(lead_id), since=NOW.isoformat()
        )
    )

    assert result.unsubscribed
    assert not result.replied


@pytest.mark.asyncio
async def test_check_conversation_finds_no_reply_before_the_send(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        lead_id, _campaign_id, _step_id = await _seed_lead_and_campaign(
            seed_session, org_a, email="prospect6@a.example"
        )
        conversations = await SqlAlchemyConversationRepository.create(seed_session, org_a)
        conversation = await conversations.add(lead_id=lead_id, channel="email")
        stale_activity = NOW - timedelta(days=1)
        await conversations.touch_last_activity(conversation.id, at=stale_activity)

    result = await check_conversation_activity(
        CheckConversationInput(
            organization_id=str(org_a), lead_id=str(lead_id), since=NOW.isoformat()
        )
    )

    assert not result.replied
    assert not result.unsubscribed
