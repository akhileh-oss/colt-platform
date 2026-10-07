"""Milestone 22's acceptance criterion, proven literally: "Dashboard can answer what segments,
signals, personas, channels and message variants produce commercial outcomes" (CLAUDE.md §68).

**What this proves for real, against real Postgres:**

A company that wins (closed-won `Opportunity`) carries a distinct industry, a distinct signal
type, a distinct message prompt version + recipient persona, and a distinct channel from a
company that never converts. Reading every row back through each repository's real `list_all()`
and feeding it to the matching `colt_application.summarize_*` pure function surfaces the winning
company's segment, signal, message variant/persona, and channel with a nonzero commercial-outcome
metric (`won_revenue`, `won_company_count`, `approved_count`/`sent_count`, `positive_rate`) while
the non-converting company's dimension stays at zero — exactly the dashboard's own job, not a
fabricated number (CLAUDE.md §0.4).

A second test proves the three purely operational reports (`funnel`, `agent cost`, `model
performance`) and `revenue outcomes` reflect real rows the same way.

**What this environment cannot prove, and why:**

Every row here is seeded directly through repositories, the same "no real Anthropic key" caveat
carried since Milestone 08 — no agent call produces any of this data in this test. Each
`summarize_*` function's own hermetic unit tests already prove the aggregation logic in isolation
(grouping, fallbacks, sorting); this test proves the real repositories' `list_all()` methods feed
those functions real rows end to end, against real RLS-scoped Postgres.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

from colt_application import (
    summarize_agent_cost,
    summarize_channel_performance,
    summarize_funnel,
    summarize_icp_performance,
    summarize_message_performance,
    summarize_model_performance,
    summarize_revenue_by_source,
    summarize_trigger_performance,
)
from colt_application.use_cases.create_or_update_opportunity import CreateOrUpdateOpportunity
from colt_application.use_cases.transition_opportunity_stage import TransitionOpportunityStage
from colt_db.repositories.agent_run_repository import SqlAlchemyAgentRunRepository
from colt_db.repositories.campaign_repository import SqlAlchemyCampaignRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.conversation_repository import SqlAlchemyConversationRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.message_repository import SqlAlchemyMessageRepository
from colt_db.repositories.opportunity_repository import SqlAlchemyOpportunityRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_db.repositories.signal_repository import SqlAlchemySignalRepository
from colt_domain import ConversationState, LeadStatus, PipelineStage

SessionFactory = Any
NOW = datetime.now(UTC)


@pytest.mark.asyncio
async def test_dashboard_can_answer_what_segments_signals_personas_channels_and_message_variants_produce_commercial_outcomes(  # noqa: E501
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        companies = await SqlAlchemyCompanyRepository.create(seed_session, org_a)
        persons = SqlAlchemyPersonRepository(seed_session, org_a)
        leads = SqlAlchemyLeadRepository(seed_session, org_a)
        signals = SqlAlchemySignalRepository(seed_session, org_a)
        campaigns = SqlAlchemyCampaignRepository(seed_session, org_a)
        messages = SqlAlchemyMessageRepository(seed_session, org_a)
        conversations = SqlAlchemyConversationRepository(seed_session, org_a)
        opportunities = SqlAlchemyOpportunityRepository(seed_session, org_a)

        campaign = await campaigns.add(name="Q1 outbound")

        # The winning company: aerospace, a funding-round signal, a VP recipient on message
        # variant "v1", contacted over email — every dimension this test checks.
        winner = await companies.add(name="Acme Rockets", industry="aerospace")
        winner_person = await persons.add(company_id=winner.id, full_name="Dana VP", seniority="VP")
        winner_lead = await leads.add(
            company_id=winner.id, person_id=winner_person.id, status=LeadStatus.ENGAGED
        )
        await signals.add(
            company_id=winner.id, signal_type="funding_round", observed_at=NOW, confidence=0.9
        )
        await messages.add(
            campaign_id=campaign.id,
            lead_id=winner_lead.id,
            channel="email",
            body="Congrats on the raise.",
            prompt_version="v1",
            status="SENT",
            approval_status="APPROVED",
        )
        await conversations.add(
            lead_id=winner_lead.id, channel="email", state=ConversationState.POSITIVE
        )
        await CreateOrUpdateOpportunity(opportunities)(
            company_id=winner.id,
            source="conversation",
            estimated_value=20000.0,
            currency="USD",
            now=NOW,
        )
        won = await opportunities.get_open_by_company(winner.id)
        assert won is not None
        transition = TransitionOpportunityStage(opportunities)
        for stage in (
            PipelineStage.DISCOVERY,
            PipelineStage.EVALUATION,
            PipelineStage.PROPOSAL,
            PipelineStage.NEGOTIATION,
            PipelineStage.WON,
        ):
            await transition(won.id, stage, now=NOW)

        # The non-converting company: a different industry, no signal, a different message
        # variant/persona/channel, no opportunity at all.
        other = await companies.add(name="Beta Corp", industry="retail")
        other_person = await persons.add(company_id=other.id, full_name="Ian IC", seniority="IC")
        other_lead = await leads.add(
            company_id=other.id, person_id=other_person.id, status=LeadStatus.CONTACTED
        )
        await messages.add(
            campaign_id=campaign.id,
            lead_id=other_lead.id,
            channel="linkedin",
            body="Checking in.",
            prompt_version="v2",
            status="DRAFT",
            approval_status="PENDING",
        )
        await conversations.add(
            lead_id=other_lead.id, channel="linkedin", state=ConversationState.OPEN
        )

    read_session = await open_app_session()
    async with read_session, read_session.begin():
        companies_read = await SqlAlchemyCompanyRepository.create(read_session, org_a)
        leads_read = SqlAlchemyLeadRepository(read_session, org_a)
        persons_read = SqlAlchemyPersonRepository(read_session, org_a)
        signals_read = SqlAlchemySignalRepository(read_session, org_a)
        messages_read = SqlAlchemyMessageRepository(read_session, org_a)
        conversations_read = SqlAlchemyConversationRepository(read_session, org_a)
        opportunities_read = SqlAlchemyOpportunityRepository(read_session, org_a)

        all_companies = await companies_read.list_all()
        all_leads = await leads_read.list_all()
        all_persons = await persons_read.list_all()
        all_signals = await signals_read.list_all()
        all_messages = await messages_read.list_all()
        all_conversations = await conversations_read.list_all()
        all_opportunities = await opportunities_read.list_all()

    # Segment (ICP/industry): the winning segment shows the won revenue, the other does not.
    icp_rows = {
        row.industry: row
        for row in summarize_icp_performance(all_companies, all_leads, all_opportunities)
    }
    assert icp_rows["aerospace"].won_company_count == 1
    assert icp_rows["aerospace"].won_revenue == 20000.0
    assert icp_rows["retail"].won_company_count == 0
    assert icp_rows["retail"].won_revenue == 0.0

    # Signal (trigger): only the signal type on the winning company shows a won company.
    trigger_rows = {
        row.signal_type: row
        for row in summarize_trigger_performance(all_signals, all_opportunities)
    }
    assert trigger_rows["funding_round"].won_company_count == 1
    assert trigger_rows["funding_round"].average_confidence == 0.9

    # Message variant + persona: "v1"/VP was sent and approved; "v2"/IC was neither.
    message_rows = {
        (row.prompt_version, row.persona): row
        for row in summarize_message_performance(all_messages, all_leads, all_persons)
    }
    assert message_rows[("v1", "VP")].sent_count == 1
    assert message_rows[("v1", "VP")].approved_count == 1
    assert message_rows[("v2", "IC")].sent_count == 0
    assert message_rows[("v2", "IC")].approved_count == 0

    # Channel: email (the winning channel) has a positive conversation; linkedin does not.
    channel_rows = {
        row.channel: row for row in summarize_channel_performance(all_messages, all_conversations)
    }
    assert channel_rows["email"].positive_rate == 1.0
    assert channel_rows["linkedin"].positive_rate == 0.0


@pytest.mark.asyncio
async def test_funnel_agent_cost_model_performance_and_revenue_outcomes_reflect_real_rows(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        companies = await SqlAlchemyCompanyRepository.create(seed_session, org_a)
        persons = SqlAlchemyPersonRepository(seed_session, org_a)
        leads = SqlAlchemyLeadRepository(seed_session, org_a)
        opportunities = SqlAlchemyOpportunityRepository(seed_session, org_a)
        agent_runs = await SqlAlchemyAgentRunRepository.create(seed_session, org_a)

        company = await companies.add(name="Acme Rockets")
        first_person = await persons.add(company_id=company.id, full_name="Dana VP")
        second_person = await persons.add(company_id=company.id, full_name="Pat IC")
        await leads.add(company_id=company.id, person_id=first_person.id, status=LeadStatus.NEW)
        await leads.add(
            company_id=company.id, person_id=second_person.id, status=LeadStatus.QUALIFIED
        )

        await CreateOrUpdateOpportunity(opportunities)(
            company_id=company.id,
            source="conversation",
            estimated_value=5000.0,
            currency="USD",
            now=NOW,
        )
        won = await opportunities.get_open_by_company(company.id)
        assert won is not None
        transition = TransitionOpportunityStage(opportunities)
        for stage in (
            PipelineStage.DISCOVERY,
            PipelineStage.EVALUATION,
            PipelineStage.PROPOSAL,
            PipelineStage.NEGOTIATION,
            PipelineStage.WON,
        ):
            await transition(won.id, stage, now=NOW)

        completed_run = await agent_runs.start(
            agent_name="ScoringAgent",
            agent_version="v1",
            model_name="claude-opus-5",
            input_hash="hash-1",
        )
        await agent_runs.complete(
            completed_run.id,
            at=NOW,
            input_tokens=100,
            output_tokens=50,
            tool_tokens=0,
            estimated_cost_usd=0.05,
            output_json=None,
        )
        failed_run = await agent_runs.start(
            agent_name="ScoringAgent",
            agent_version="v1",
            model_name="claude-opus-5",
            input_hash="hash-2",
        )
        await agent_runs.fail(failed_run.id, at=NOW, error_code="timeout", error_message="boom")

    read_session = await open_app_session()
    async with read_session, read_session.begin():
        leads_read = SqlAlchemyLeadRepository(read_session, org_a)
        opportunities_read = SqlAlchemyOpportunityRepository(read_session, org_a)
        agent_runs_read = await SqlAlchemyAgentRunRepository.create(read_session, org_a)

        all_leads = await leads_read.list_all()
        all_opportunities = await opportunities_read.list_all()
        all_agent_runs = await agent_runs_read.list_all()

    funnel_rows = {row.status: row for row in summarize_funnel(all_leads)}
    assert funnel_rows[LeadStatus.NEW].count == 1
    assert funnel_rows[LeadStatus.QUALIFIED].count == 1
    assert funnel_rows[LeadStatus.ENGAGED].count == 0

    agent_cost_rows = {row.agent_name: row for row in summarize_agent_cost(all_agent_runs)}
    assert agent_cost_rows["ScoringAgent"].run_count == 2
    assert agent_cost_rows["ScoringAgent"].total_cost_usd == 0.05

    model_rows = {row.model_name: row for row in summarize_model_performance(all_agent_runs)}
    assert model_rows["claude-opus-5"].completed_count == 1
    assert model_rows["claude-opus-5"].failed_count == 1
    assert model_rows["claude-opus-5"].success_rate == 0.5

    revenue_rows = {row.source: row for row in summarize_revenue_by_source(all_opportunities)}
    assert revenue_rows["conversation"].total_value == 5000.0
    assert revenue_rows["conversation"].opportunity_count == 1
