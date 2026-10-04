"""Milestone 13's acceptance criterion, proven literally: "Scores are reproducible from
persisted inputs and rules" (CLAUDE.md §68).

Everything here is real except the Anthropic call itself: real Postgres, real RLS, a real
seeded `Lead` (via `SqlAlchemyCompanyRepository`/`SqlAlchemyPersonRepository`/
`SqlAlchemyLeadRepository`), and a real `ScoreLead` use case backed by
`SqlAlchemyLeadScoreRepository`. `overall_score`/`reason_codes` are independently recomputed
from the persisted `LeadScore` row's own five component fields, queried back from Postgres,
and compared against what the agent actually returned - not asserted from in-memory state.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr
from sqlalchemy import text

from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.scoring_agent import (
    SCORING_AGENT_DEFINITION,
    ScoringAgentInput,
    ScoringAgentOutput,
)
from colt_agents.tools import build_score_lead_tool
from colt_ai import AnthropicGateway
from colt_application.scoring import compute_overall_score, determine_reason_codes
from colt_application.use_cases.score_lead import ScoreLead
from colt_config import AnthropicSettings
from colt_db.repositories.agent_run_repository import SqlAlchemyAgentRunRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.lead_repository import SqlAlchemyLeadRepository
from colt_db.repositories.lead_score_repository import SqlAlchemyLeadScoreRepository
from colt_db.repositories.person_repository import SqlAlchemyPersonRepository
from colt_db.repositories.tool_call_repository import SqlAlchemyToolCallRepository


def _usage() -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
    )


@pytest.mark.asyncio
async def test_a_leads_score_is_reproducible_from_its_persisted_inputs_and_rules(
    open_app_session: Any, two_organizations: tuple[Any, Any]
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

    component_scores = {
        "icp_fit": 0.9,
        "persona_fit": 0.9,
        "signal_strength": 0.9,
        "timing": 0.9,
        "model_assessment": 0.9,
    }

    calls: list[dict[str, Any]] = []

    async def fake_create(**kwargs: Any) -> Message:
        calls.append(kwargs)
        if len(calls) == 1:
            return Message(
                id="msg_1",
                content=[
                    ToolUseBlock(
                        id="toolu_1",
                        input={"lead_id": str(lead.id), **component_scores},
                        name="score_lead",
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
        output = ScoringAgentOutput(
            lead_score_id=UUID(result["lead_score_id"]),
            persona_fit=component_scores["persona_fit"],
            model_assessment=component_scores["model_assessment"],
            overall_score=result["overall_score"],
            reason_codes=result["reason_codes"],
            qualified=result["qualified"],
        )
        return Message(
            id="msg_2",
            content=[TextBlock(text=output.model_dump_json(), type="text")],
            model=kwargs["model"],
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage=_usage(),
        )

    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    client.messages.create = fake_create  # type: ignore[assignment]
    gateway = AnthropicGateway(
        AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )

    session = await open_app_session()
    async with session, session.begin():
        lead_scores = await SqlAlchemyLeadScoreRepository.create(session, org_a)
        leads = SqlAlchemyLeadRepository(session, org_a)
        registry = ToolRegistry()
        registry.register(build_score_lead_tool(ScoreLead(lead_scores, leads)))
        agent_runs = SqlAlchemyAgentRunRepository(session, org_a)
        tool_calls = SqlAlchemyToolCallRepository(session, org_a)
        runtime = AgentRuntime(gateway, registry, agent_runs, tool_calls)

        output = await runtime.run(
            SCORING_AGENT_DEFINITION,
            input=ScoringAgentInput(
                lead_id=lead.id,
                icp_fit=component_scores["icp_fit"],
                signal_strength=component_scores["signal_strength"],
                timing=component_scores["timing"],
            ),
        )

        score_rows = (
            (
                await session.execute(
                    text("SELECT * FROM lead_scores WHERE organization_id = :org"), {"org": org_a}
                )
            )
            .mappings()
            .all()
        )
        lead_rows = (
            (await session.execute(text("SELECT * FROM leads WHERE id = :id"), {"id": lead.id}))
            .mappings()
            .all()
        )

    assert isinstance(output, ScoringAgentOutput)
    assert len(score_rows) == 1
    score_row = score_rows[0]

    # Independently recompute overall_score/reason_codes from the persisted row's own fields -
    # not from in-memory state - and show they match the rules exactly.
    recomputed_overall = compute_overall_score(
        icp_fit=score_row["icp_fit"],
        persona_fit=score_row["persona_fit"],
        signal_strength=score_row["signal_strength"],
        timing=score_row["timing"],
        model_assessment=score_row["model_assessment"],
    )
    recomputed_codes = determine_reason_codes(
        icp_fit=score_row["icp_fit"],
        persona_fit=score_row["persona_fit"],
        signal_strength=score_row["signal_strength"],
        timing=score_row["timing"],
        overall_score=recomputed_overall,
    )
    assert score_row["overall_score"] == pytest.approx(recomputed_overall)
    assert output.overall_score == pytest.approx(recomputed_overall)
    assert set(score_row["reason_codes"]) == set(recomputed_codes)
    assert set(output.reason_codes) == set(recomputed_codes)

    assert lead_rows[0]["status"] == "QUALIFIED"
    assert output.qualified is True
