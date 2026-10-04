"""Milestone 10's acceptance criterion, proven literally: "A company can be researched and
every factual claim produced by the agent is linked to stored evidence" (CLAUDE.md §68).

Everything in this test is real except the Anthropic call itself: real Postgres, real RLS, a
real `Company` seeded through `SqlAlchemyCompanyRepository`, a real `RecordEvidence` use case
backed by `SqlAlchemyEvidenceRepository`, and a real `HttpFetchProvider` fetching an actual page
over the network (`https://example.com`) — only `search_web`'s results are a `FakeSearchProvider`
fixture, since no real search-provider key exists in this environment (same situation `colt_ai`
is in with Anthropic). The one substitution is a real `AsyncAnthropic` instance with only
`.messages.create` replaced. See Milestone 08/09's PRs, and this one's, for what that leaves
unverified.

Requires a real Postgres and real network access. Marked `integration`.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from uuid import UUID

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from colt_agents import AgentRuntime, ToolRegistry
from colt_agents.research_agent import (
    RESEARCH_AGENT_DEFINITION,
    ClaimType,
    DossierClaim,
    ResearchAgentInput,
    ResearchDossier,
)
from colt_agents.tools import (
    build_fetch_page_tool,
    build_record_evidence_tool,
    build_search_web_tool,
)
from colt_ai import AnthropicGateway
from colt_application import RecordEvidence
from colt_config import AnthropicSettings, SecuritySettings
from colt_db.repositories.agent_run_repository import SqlAlchemyAgentRunRepository
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from colt_db.repositories.tool_call_repository import SqlAlchemyToolCallRepository
from colt_integrations.fetch.http import HttpFetchProvider
from colt_integrations.search.fake import FakeSearchProvider
from colt_integrations.search.port import SearchResult

SessionFactory = Any


def _usage(input_tokens: int = 10, output_tokens: int = 5) -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


@pytest.mark.asyncio
async def test_a_company_can_be_researched_and_every_fact_claim_links_to_stored_evidence(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        company_repo = await SqlAlchemyCompanyRepository.create(seed, org_a)
        company = await company_repo.add(name="Acme Rockets", domain="example.com")

    search_provider = FakeSearchProvider(
        {
            "Acme Rockets": [
                SearchResult(
                    title="Example Domain",
                    url="https://example.com",
                    snippet="This domain is for use in illustrative examples.",
                )
            ]
        }
    )
    fetch_provider = HttpFetchProvider(SecuritySettings())

    tool_use_blocks = [
        ToolUseBlock(
            id="toolu_1",
            input={"query": "Acme Rockets", "max_results": 5},
            name="search_web",
            type="tool_use",
        ),
        ToolUseBlock(
            id="toolu_2", input={"url": "https://example.com"}, name="fetch_page", type="tool_use"
        ),
    ]

    calls: list[dict[str, Any]] = []
    recorded_evidence_id: UUID | None = None

    async def fake_create(**kwargs: Any) -> Message:
        nonlocal recorded_evidence_id
        calls.append(kwargs)
        turn = len(calls)
        if turn <= 2:
            return Message(
                id=f"msg_{turn}",
                content=[tool_use_blocks[turn - 1]],
                model=kwargs["model"],
                role="assistant",
                stop_reason="tool_use",
                stop_sequence=None,
                type="message",
                usage=_usage(),
            )
        if turn == 3:
            return Message(
                id="msg_3",
                content=[
                    ToolUseBlock(
                        id="toolu_3",
                        input={
                            "entity_type": "company",
                            "entity_id": str(company.id),
                            "claim": "Acme Rockets' site is reachable at example.com.",
                            "source_url": "https://example.com",
                            "source_date": date.today().isoformat(),
                        },
                        name="record_evidence",
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
        recorded_evidence_id = UUID(json.loads(last_tool_result["content"])["evidence_id"])
        dossier = ResearchDossier(
            company_id=company.id,
            summary="Acme Rockets maintains a reachable website at example.com.",
            claims=[
                DossierClaim(
                    claim_type=ClaimType.FACT,
                    text="Acme Rockets' site is reachable at example.com.",
                    evidence_ids=[recorded_evidence_id],
                )
            ],
        )
        return Message(
            id="msg_4",
            content=[TextBlock(text=dossier.model_dump_json(), type="text")],
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

    session: AsyncSession = await open_app_session()
    async with session, session.begin():
        evidence_repo = await SqlAlchemyEvidenceRepository.create(session, org_a)
        record_evidence = RecordEvidence(evidence_repo)

        registry = ToolRegistry()
        registry.register(build_search_web_tool(search_provider))
        registry.register(build_fetch_page_tool(fetch_provider))
        registry.register(build_record_evidence_tool(record_evidence))

        agent_runs = SqlAlchemyAgentRunRepository(session, org_a)
        tool_calls = SqlAlchemyToolCallRepository(session, org_a)
        runtime = AgentRuntime(gateway, registry, agent_runs, tool_calls)

        output = await runtime.run(
            RESEARCH_AGENT_DEFINITION,
            input=ResearchAgentInput(
                company_id=company.id, company_name="Acme Rockets", company_domain="example.com"
            ),
        )

        evidence_rows = (
            (
                await session.execute(
                    text("SELECT * FROM evidence WHERE organization_id = :org"), {"org": org_a}
                )
            )
            .mappings()
            .all()
        )
        tool_call_rows = (
            (
                await session.execute(
                    text("SELECT * FROM tool_calls WHERE organization_id = :org"), {"org": org_a}
                )
            )
            .mappings()
            .all()
        )

    assert isinstance(output, ResearchDossier)
    fact_claims = [claim for claim in output.claims if claim.claim_type == ClaimType.FACT]
    assert fact_claims, "the dossier must contain at least one FACT claim"

    # Every FACT claim's evidence_ids correspond to a real row, independently queried back from
    # Postgres - not merely asserted from in-memory state.
    assert len(evidence_rows) == 1
    evidence_row = evidence_rows[0]
    for claim in fact_claims:
        assert claim.evidence_ids
        for evidence_id in claim.evidence_ids:
            assert str(evidence_id) == str(evidence_row["id"])
    assert evidence_row["claim"] == "Acme Rockets' site is reachable at example.com."
    assert evidence_row["source_url"] == "https://example.com"
    assert evidence_row["verification_status"] == "UNVERIFIED"

    # fetch_page really hit the network - the fetched title proves it, not a fixture.
    fetch_call = next(row for row in tool_call_rows if row["tool_name"] == "fetch_page")
    assert "Example Domain" in fetch_call["result_summary"]
