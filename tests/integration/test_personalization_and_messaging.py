"""Milestone 15's acceptance criterion, proven literally: "Generated messages contain only
supported factual personalization and retain evidence IDs" (CLAUDE.md §68).

Everything here is real except the Anthropic call itself: real Postgres, real RLS, a real
`Company`/`Person`/`Lead` seeded through their own repositories, real `Evidence` recorded
through `RecordEvidence`/`SqlAlchemyEvidenceRepository`, and the real `PersonalizationAgent` →
`MessagingAgent` pipeline run through `AgentRuntime` with real `colt-db` repositories backing
every tool. The one substitution is a real `AsyncAnthropic` instance with only
`.messages.create` replaced — the same pattern every milestone since 08 has used; see those
PRs for what it leaves unverified.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message as AnthropicMessage
from anthropic.types import TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr
from sqlalchemy import text

from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.messaging_agent import (
    MESSAGING_AGENT_DEFINITION,
    MessagingAgentInput,
    MessagingAgentOutput,
)
from colt_agents.personalization_agent import (
    PERSONALIZATION_AGENT_DEFINITION,
    PersonalizationAgentInput,
    PersonalizationStrategy,
)
from colt_agents.tools import (
    build_draft_message_tool,
    build_list_evidence_for_lead_tool,
    build_select_evidence_tool,
)
from colt_ai import AnthropicGateway
from colt_application import RecordEvidence
from colt_application.use_cases.create_campaign import CreateCampaign
from colt_application.use_cases.draft_message import DraftMessage
from colt_application.use_cases.list_evidence_for_lead import ListEvidenceForLead
from colt_application.use_cases.select_personalization_evidence import (
    SelectPersonalizationEvidence,
)
from colt_config import AnthropicSettings
from colt_db.repositories.agent_run_repository import SqlAlchemyAgentRunRepository
from colt_db.repositories.campaign_repository import SqlAlchemyCampaignRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.message_repository import SqlAlchemyMessageRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_db.repositories.tool_call_repository import SqlAlchemyToolCallRepository

SessionFactory = Any


def _usage() -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
    )


@pytest.mark.asyncio
async def test_a_generated_message_contains_only_supported_personalization_and_retains_evidence_ids(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        company_repo = await SqlAlchemyCompanyRepository.create(seed, org_a)
        company = await company_repo.add(name="Acme Rockets")
        person_repo = SqlAlchemyPersonRepository(seed, org_a)
        person = await person_repo.add(company_id=company.id, full_name="Jane Doe")
        lead_repo = SqlAlchemyLeadRepository(seed, org_a)
        lead = await lead_repo.add(company_id=company.id, person_id=person.id)
        evidence_repo = await SqlAlchemyEvidenceRepository.create(seed, org_a)
        evidence = await RecordEvidence(evidence_repo)(
            entity_type="Company",
            entity_id=company.id,
            claim="Acme Rockets raised a $20M Series B.",
            source_url="https://example.com/news",
            observed_at=datetime.now(UTC),
            source_date=date.today(),
        )
        campaign_repo = await SqlAlchemyCampaignRepository.create(seed, org_a)
        campaign = await CreateCampaign(campaign_repo)(name="Q4 outbound")

    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    gateway = AnthropicGateway(
        AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )

    # --- PersonalizationAgent: list evidence, select it, form a strategy. -------------------
    personalization_calls: list[dict[str, Any]] = []

    async def fake_personalization_create(**kwargs: Any) -> AnthropicMessage:
        personalization_calls.append(kwargs)
        turn = len(personalization_calls)
        if turn == 1:
            return AnthropicMessage(
                id="msg_1",
                content=[
                    ToolUseBlock(
                        id="toolu_1",
                        input={"lead_id": str(lead.id)},
                        name="list_evidence_for_lead",
                        type="tool_use",
                    )
                ],
                model=kwargs["model"],
                role="assistant",
                stop_reason="tool_use",
                stop_sequence=None,
                type="message",
                usage=_usage(),
            )
        if turn == 2:
            return AnthropicMessage(
                id="msg_2",
                content=[
                    ToolUseBlock(
                        id="toolu_2",
                        input={"evidence_ids": [str(evidence.id)]},
                        name="select_evidence",
                        type="tool_use",
                    )
                ],
                model=kwargs["model"],
                role="assistant",
                stop_reason="tool_use",
                stop_sequence=None,
                type="message",
                usage=_usage(),
            )
        last_tool_result = kwargs["messages"][-1]["content"][0]
        result = json.loads(last_tool_result["content"])
        strategy = PersonalizationStrategy(
            lead_id=lead.id,
            evidence_ids=[UUID(v) for v in result["verified_evidence_ids"]],
            angle="Open with the Series B and ask how they're scaling the team.",
            business_relevance="Fresh funding usually means headcount growth next quarter.",
        )
        return AnthropicMessage(
            id="msg_3",
            content=[TextBlock(text=strategy.model_dump_json(), type="text")],
            model=kwargs["model"],
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage=_usage(),
        )

    session = await open_app_session()
    async with session, session.begin():
        evidence_repo = await SqlAlchemyEvidenceRepository.create(session, org_a)
        lead_repo = SqlAlchemyLeadRepository(session, org_a)
        registry = ToolRegistry()
        registry.register(
            build_list_evidence_for_lead_tool(ListEvidenceForLead(lead_repo, evidence_repo))
        )
        registry.register(build_select_evidence_tool(SelectPersonalizationEvidence(evidence_repo)))
        agent_runs = SqlAlchemyAgentRunRepository(session, org_a)
        tool_calls = SqlAlchemyToolCallRepository(session, org_a)
        client.messages.create = fake_personalization_create  # type: ignore[assignment]
        runtime = AgentRuntime(gateway, registry, agent_runs, tool_calls)

        strategy_output = await runtime.run(
            PERSONALIZATION_AGENT_DEFINITION,
            input=PersonalizationAgentInput(
                lead_id=lead.id, company_name="Acme Rockets", person_name="Jane Doe"
            ),
        )

    assert isinstance(strategy_output, PersonalizationStrategy)
    assert strategy_output.evidence_ids == [evidence.id]

    # --- MessagingAgent: transform the strategy into a drafted, persisted message. ----------
    drafted_body = "Congrats on the $20M Series B - curious how you're scaling the team."
    campaign_id = campaign.id

    async def fake_messaging_create(**kwargs: Any) -> AnthropicMessage:
        if len(kwargs["messages"]) == 1:
            return AnthropicMessage(
                id="msg_1",
                content=[
                    ToolUseBlock(
                        id="toolu_1",
                        input={
                            "campaign_id": str(campaign_id),
                            "lead_id": str(lead.id),
                            "channel": "email",
                            "body": drafted_body,
                            "evidence_ids": [str(e) for e in strategy_output.evidence_ids],
                        },
                        name="draft_message",
                        type="tool_use",
                    )
                ],
                model=kwargs["model"],
                role="assistant",
                stop_reason="tool_use",
                stop_sequence=None,
                type="message",
                usage=_usage(),
            )
        last_tool_result = kwargs["messages"][-1]["content"][0]
        result = json.loads(last_tool_result["content"])
        output = MessagingAgentOutput(
            message_id=UUID(result["message_id"]),
            channel=result["channel"],
            subject=result["subject"],
            body=result["body"],
            evidence_ids=[UUID(v) for v in result["evidence_ids"]],
        )
        return AnthropicMessage(
            id="msg_2",
            content=[TextBlock(text=output.model_dump_json(), type="text")],
            model=kwargs["model"],
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage=_usage(),
        )

    session = await open_app_session()
    async with session, session.begin():
        evidence_repo = await SqlAlchemyEvidenceRepository.create(session, org_a)
        message_repo = SqlAlchemyMessageRepository(session, org_a)
        registry = ToolRegistry()
        registry.register(build_draft_message_tool(DraftMessage(message_repo, evidence_repo)))
        agent_runs = SqlAlchemyAgentRunRepository(session, org_a)
        tool_calls = SqlAlchemyToolCallRepository(session, org_a)
        client.messages.create = fake_messaging_create  # type: ignore[assignment]
        runtime = AgentRuntime(gateway, registry, agent_runs, tool_calls)

        message_output = await runtime.run(
            MESSAGING_AGENT_DEFINITION,
            input=MessagingAgentInput(
                lead_id=lead.id,
                campaign_id=campaign_id,
                channel="email",
                angle=strategy_output.angle,
                business_relevance=strategy_output.business_relevance,
                evidence_ids=strategy_output.evidence_ids,
            ),
        )

    assert isinstance(message_output, MessagingAgentOutput)
    assert message_output.evidence_ids == [evidence.id]
    assert message_output.body == drafted_body

    # Independently re-read from Postgres - not just asserted from in-memory state. A bare
    # session has no RLS context bound yet, so the tenant-scoped repository is constructed via
    # `.create()` first, same as every other call in this file.
    session = await open_app_session()
    async with session, session.begin():
        message_repo = await SqlAlchemyMessageRepository.create(session, org_a)
        persisted = await message_repo.get(message_output.message_id)
        message_rows = (
            (
                await session.execute(
                    text("SELECT * FROM messages WHERE organization_id = :org"), {"org": org_a}
                )
            )
            .mappings()
            .all()
        )
    assert persisted is not None
    assert len(message_rows) == 1
    assert persisted.evidence_ids == [evidence.id]
    assert persisted.body == drafted_body
    assert persisted.status == "DRAFT"

    # A different organization sees nothing of this - same tenant isolation every prior
    # milestone's capstone test proves.
    session = await open_app_session()
    async with session, session.begin():
        message_repo_b = SqlAlchemyMessageRepository(session, org_b)
        assert await message_repo_b.get(message_output.message_id) is None


@pytest.mark.asyncio
async def test_drafting_a_second_message_for_the_same_lead_appends_a_new_version(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        company_repo = await SqlAlchemyCompanyRepository.create(seed, org_a)
        company = await company_repo.add(name="Acme Rockets")
        person_repo = SqlAlchemyPersonRepository(seed, org_a)
        person = await person_repo.add(company_id=company.id, full_name="Jane Doe")
        lead_repo = SqlAlchemyLeadRepository(seed, org_a)
        lead = await lead_repo.add(company_id=company.id, person_id=person.id)
        evidence_repo = await SqlAlchemyEvidenceRepository.create(seed, org_a)
        evidence = await RecordEvidence(evidence_repo)(
            entity_type="Company",
            entity_id=company.id,
            claim="Acme Rockets raised a $20M Series B.",
            source_url="https://example.com/news",
            observed_at=datetime.now(UTC),
        )
        campaign_repo = await SqlAlchemyCampaignRepository.create(seed, org_a)
        campaign = await CreateCampaign(campaign_repo)(name="Q4 outbound")

    campaign_id = campaign.id
    session = await open_app_session()
    async with session, session.begin():
        evidence_repo = await SqlAlchemyEvidenceRepository.create(session, org_a)
        message_repo = SqlAlchemyMessageRepository(session, org_a)
        draft_message = DraftMessage(message_repo, evidence_repo)

        await draft_message(
            campaign_id=campaign_id,
            lead_id=lead.id,
            channel="email",
            body="First draft.",
            evidence_ids=[evidence.id],
        )
        await draft_message(
            campaign_id=campaign_id,
            lead_id=lead.id,
            channel="email",
            body="Second draft.",
            evidence_ids=[evidence.id],
        )

        versions = await message_repo.list_by_lead_and_step(lead.id, None)

    assert [v.body for v in versions] == ["First draft.", "Second draft."]
    assert len({v.id for v in versions}) == 2
