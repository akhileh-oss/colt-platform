"""Milestone 19's acceptance criterion, proven literally: "Incoming replies update the
conversation state deterministically and high-intent replies produce the correct handoff"
(CLAUDE.md §68).

Everything here is real: real Postgres, real RLS (`SqlAlchemyConversationRepository.create`),
and the real `RecordReplyClassification` use case applying
`colt_application.reply_classification.determine_conversation_transition`. No real Anthropic
key exists in this environment (the caveat carried since Milestone 08), so
`ReplyIntelligenceAgent` itself is proven hermetically only
(`packages/python/colt-agents/tests/test_colt_agents_reply_intelligence_agent.py`) — this test
proves the deterministic half of the pipeline the acceptance criterion actually asks for:
given a classification (however it was produced), does the right thing happen to the real
`Conversation` row and its `ConversationEvent` history.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select

from colt_application.reply_classification import Urgency
from colt_application.use_cases.record_reply_classification import RecordReplyClassification
from colt_db.models.conversation_event import ConversationEventModel
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.conversation_event_repository import (
    SqlAlchemyConversationEventRepository,
)
from colt_db.repositories.conversation_repository import SqlAlchemyConversationRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_domain import ConversationState

SessionFactory = Any
NOW = datetime.now(UTC)


async def _seed_lead(session: Any, org_id: UUID) -> UUID:
    """`conversations.lead_id` has a real foreign key to `leads.id` — a conversation needs a
    real lead to attach to, the same way `test_policy_and_approval.py`'s own seeding does."""
    companies = await SqlAlchemyCompanyRepository.create(session, org_id)
    company = await companies.add(name="Acme Rockets")
    persons = SqlAlchemyPersonRepository(session, org_id)
    person = await persons.add(company_id=company.id, full_name="Jane Doe", email="jane@a.example")
    leads = SqlAlchemyLeadRepository(session, org_id)
    lead = await leads.add(company_id=company.id, person_id=person.id)
    return lead.id


@pytest.mark.asyncio
async def test_a_high_urgency_reply_deterministically_produces_a_handoff(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        conversations = await SqlAlchemyConversationRepository.create(seed_session, org_a)
        conversation = await conversations.add(
            lead_id=await _seed_lead(seed_session, org_a), channel="email"
        )
        conversation_events = SqlAlchemyConversationEventRepository(seed_session, org_a)
        record = RecordReplyClassification(conversations, conversation_events)

        # The model recommended QUESTION — only HIGH urgency decides the actual outcome.
        await record(
            conversation.id,
            intent="MEETING_REQUEST",
            sentiment="POSITIVE",
            urgency=Urgency.HIGH,
            objection=None,
            asks_question=True,
            meeting_signal=True,
            recommended_state_transition=ConversationState.QUESTION,
            confidence=0.9,
            suggested_response="Happy to set up a call this week.",
            now=NOW,
        )

    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        conversations_verify = await SqlAlchemyConversationRepository.create(verify_session, org_a)
        reread = await conversations_verify.get(conversation.id)
        assert reread is not None
        assert reread.state == ConversationState.HUMAN_HANDOFF

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
        event_types = {row.event_type for row in rows}
        assert {"reply_classified", "handoff_created"} <= event_types


@pytest.mark.asyncio
async def test_a_low_urgency_reply_applies_the_recommended_state_with_no_handoff(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        conversations = await SqlAlchemyConversationRepository.create(seed_session, org_a)
        conversation = await conversations.add(
            lead_id=await _seed_lead(seed_session, org_a), channel="email"
        )
        conversation_events = SqlAlchemyConversationEventRepository(seed_session, org_a)
        record = RecordReplyClassification(conversations, conversation_events)

        await record(
            conversation.id,
            intent="OBJECTION",
            sentiment="NEGATIVE",
            urgency=Urgency.LOW,
            objection="Not the right time of year for this.",
            asks_question=False,
            meeting_signal=False,
            recommended_state_transition=ConversationState.OBJECTION,
            confidence=0.8,
            suggested_response=None,
            now=NOW,
        )

    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        conversations_verify = await SqlAlchemyConversationRepository.create(verify_session, org_a)
        reread = await conversations_verify.get(conversation.id)
        assert reread is not None
        assert reread.state == ConversationState.OBJECTION

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
        event_types = [row.event_type for row in rows]
        assert event_types == ["reply_classified"]


@pytest.mark.asyncio
async def test_a_reply_to_an_already_unsubscribed_conversation_does_not_reopen_it(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        conversations = await SqlAlchemyConversationRepository.create(seed_session, org_a)
        conversation = await conversations.add(
            lead_id=await _seed_lead(seed_session, org_a), channel="email"
        )
        await conversations.update_state(conversation.id, ConversationState.UNSUBSCRIBED, at=NOW)
        conversation_events = SqlAlchemyConversationEventRepository(seed_session, org_a)
        record = RecordReplyClassification(conversations, conversation_events)

        await record(
            conversation.id,
            intent="INTERESTED",
            sentiment="POSITIVE",
            urgency=Urgency.HIGH,
            objection=None,
            asks_question=False,
            meeting_signal=False,
            recommended_state_transition=ConversationState.POSITIVE,
            confidence=0.7,
            suggested_response=None,
            now=NOW,
        )

    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        conversations_verify = await SqlAlchemyConversationRepository.create(verify_session, org_a)
        reread = await conversations_verify.get(conversation.id)
        assert reread is not None
        assert reread.state == ConversationState.UNSUBSCRIBED
