"""`ResearchAgent` (CLAUDE.md §12.5) — the dossier schema's validator, and the full
search → fetch → record_evidence → dossier loop through `AgentRuntime`, hermetically: fake
search/fetch providers, an in-memory `EvidenceRepository`, and a real `AsyncAnthropic` instance
with only `.messages.create` replaced (the same pattern Milestone 08/09's own tests establish).
`tests/integration/test_research_agent.py` separately proves the same mechanism against real
Postgres, proving Milestone 10's acceptance criterion literally.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr, ValidationError

from colt_agents.registry import ToolRegistry
from colt_agents.research_agent import (
    RESEARCH_AGENT_DEFINITION,
    ClaimType,
    DossierClaim,
    ResearchAgentInput,
    ResearchDossier,
)
from colt_agents.runtime import AgentRuntime
from colt_agents.tools import (
    build_fetch_page_tool,
    build_record_evidence_tool,
    build_search_web_tool,
)
from colt_ai import AnthropicGateway
from colt_application import RecordEvidence
from colt_config import AnthropicSettings
from colt_domain import AgentRun, AgentRunStatus, Evidence, ToolCall, VerificationStatus
from colt_integrations.fetch.port import FetchedDocument
from colt_integrations.search.fake import FakeSearchProvider
from colt_integrations.search.port import SearchResult


class FakeFetchProvider:
    def __init__(self, documents: dict[str, FetchedDocument]) -> None:
        self._documents = documents

    async def fetch(self, url: str) -> FetchedDocument:
        return self._documents[url]


class FakeEvidenceRepository:
    def __init__(self, organization_id: UUID) -> None:
        self.organization_id = organization_id
        self.rows: dict[UUID, Evidence] = {}

    async def add(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        claim: str,
        source_url: str,
        observed_at: datetime,
        source_type: str | None = None,
        source_date: date | None = None,
        excerpt: str | None = None,
        confidence: float | None = None,
        verification_status: VerificationStatus = VerificationStatus.UNVERIFIED,
    ) -> Evidence:
        evidence = Evidence(
            id=uuid4(),
            organization_id=self.organization_id,
            created_at=datetime.now(UTC),
            entity_type=entity_type,
            entity_id=entity_id,
            claim=claim,
            source_url=source_url,
            observed_at=observed_at,
            source_type=source_type,
            source_date=source_date,
            excerpt=excerpt,
            confidence=confidence,
            verification_status=verification_status,
        )
        self.rows[evidence.id] = evidence
        return evidence

    async def get(self, evidence_id: UUID) -> Evidence | None:
        raise NotImplementedError

    async def list_by_entity(self, entity_type: str, entity_id: UUID) -> list[Evidence]:
        raise NotImplementedError


class FakeAgentRunRepository:
    def __init__(self) -> None:
        self.organization_id = uuid4()
        self.runs: dict[UUID, AgentRun] = {}

    async def start(self, **kwargs: Any) -> AgentRun:
        run = AgentRun(
            id=uuid4(), organization_id=self.organization_id, started_at=datetime.now(UTC), **kwargs
        )
        self.runs[run.id] = run
        return run

    async def complete(self, run_id: UUID, **kwargs: Any) -> AgentRun:
        self.runs[run_id] = self.runs[run_id].completed(**kwargs)
        return self.runs[run_id]

    async def fail(self, run_id: UUID, **kwargs: Any) -> AgentRun:
        self.runs[run_id] = self.runs[run_id].failed(**kwargs)
        return self.runs[run_id]


class FakeToolCallRepository:
    def __init__(self, organization_id: UUID) -> None:
        self.organization_id = organization_id
        self.calls: dict[UUID, ToolCall] = {}

    async def start(self, **kwargs: Any) -> ToolCall:
        call = ToolCall(
            id=uuid4(), organization_id=self.organization_id, started_at=datetime.now(UTC), **kwargs
        )
        self.calls[call.id] = call
        return call

    async def succeed(self, tool_call_id: UUID, **kwargs: Any) -> ToolCall:
        self.calls[tool_call_id] = self.calls[tool_call_id].succeeded(**kwargs)
        return self.calls[tool_call_id]

    async def fail(self, tool_call_id: UUID, **kwargs: Any) -> ToolCall:
        self.calls[tool_call_id] = self.calls[tool_call_id].failed(**kwargs)
        return self.calls[tool_call_id]


def _usage(input_tokens: int = 10, output_tokens: int = 5) -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )


def _gateway(fake_create: Any) -> AnthropicGateway:
    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    client.messages.create = fake_create  # type: ignore[method-assign]
    return AnthropicGateway(
        AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )


# --- DossierClaim validator -------------------------------------------------------------------


def test_a_fact_claim_with_no_evidence_ids_is_rejected() -> None:
    with pytest.raises(ValidationError, match="FACT claim must cite"):
        DossierClaim(claim_type=ClaimType.FACT, text="Acme raised a Series B.")


def test_a_fact_claim_with_an_explicit_empty_evidence_list_is_rejected() -> None:
    with pytest.raises(ValidationError, match="FACT claim must cite"):
        DossierClaim(claim_type=ClaimType.FACT, text="Acme raised a Series B.", evidence_ids=[])


def test_a_fact_claim_with_evidence_ids_is_accepted() -> None:
    claim = DossierClaim(
        claim_type=ClaimType.FACT, text="Acme raised a Series B.", evidence_ids=[uuid4()]
    )
    assert claim.claim_type == ClaimType.FACT


@pytest.mark.parametrize("claim_type", [ClaimType.INFERENCE, ClaimType.HYPOTHESIS])
def test_inference_and_hypothesis_claims_need_no_evidence(claim_type: ClaimType) -> None:
    claim = DossierClaim(claim_type=claim_type, text="Acme is probably hiring.")
    assert claim.evidence_ids == []


# --- Full search -> fetch -> record_evidence -> dossier loop, through AgentRuntime -------------


async def test_research_agent_links_every_fact_claim_to_stored_evidence() -> None:
    company_id = uuid4()
    search_provider = FakeSearchProvider(
        {
            "Acme Rockets": [
                SearchResult(
                    title="Acme Rockets raises $20M Series B",
                    url="https://news.example.com/acme-series-b",
                    snippet="Acme Rockets announced a $20M Series B today.",
                )
            ]
        }
    )
    fetch_provider = FakeFetchProvider(
        {
            "https://news.example.com/acme-series-b": FetchedDocument(
                url="https://news.example.com/acme-series-b",
                final_url="https://news.example.com/acme-series-b",
                status_code=200,
                title="Acme Rockets raises $20M Series B",
                text="Acme Rockets today announced it has raised a $20M Series B round.",
                fetched_at=datetime.now(UTC),
            )
        }
    )
    evidence_repo = FakeEvidenceRepository(uuid4())
    record_evidence = RecordEvidence(evidence_repo)

    registry = ToolRegistry()
    registry.register(build_search_web_tool(search_provider))
    registry.register(build_fetch_page_tool(fetch_provider))
    registry.register(build_record_evidence_tool(record_evidence))

    recorded_evidence_id: UUID | None = None

    def _dossier_text() -> str:
        assert recorded_evidence_id is not None
        return ResearchDossier(
            company_id=company_id,
            summary="Acme Rockets recently raised a Series B round.",
            claims=[
                DossierClaim(
                    claim_type=ClaimType.FACT,
                    text="Acme Rockets raised a $20M Series B.",
                    evidence_ids=[recorded_evidence_id],
                ),
                DossierClaim(
                    claim_type=ClaimType.INFERENCE,
                    text="Acme Rockets is likely scaling its team after this raise.",
                ),
            ],
        ).model_dump_json()

    turn = 0

    async def fake_create(**kwargs: Any) -> Message:
        nonlocal turn, recorded_evidence_id
        turn += 1
        if turn == 1:
            return Message(
                id="msg_1",
                content=[
                    ToolUseBlock(
                        id="toolu_1",
                        input={"query": "Acme Rockets", "max_results": 5},
                        name="search_web",
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
            return Message(
                id="msg_2",
                content=[
                    ToolUseBlock(
                        id="toolu_2",
                        input={"url": "https://news.example.com/acme-series-b"},
                        name="fetch_page",
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
        if turn == 3:
            return Message(
                id="msg_3",
                content=[
                    ToolUseBlock(
                        id="toolu_3",
                        input={
                            "entity_type": "company",
                            "entity_id": str(company_id),
                            "claim": "Acme Rockets raised a $20M Series B.",
                            "source_url": "https://news.example.com/acme-series-b",
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
        # The record_evidence tool_result from turn 3 carries the evidence_id the model needs
        # to cite in its final dossier - read it back out of the last message sent to the model.
        last_tool_result = kwargs["messages"][-1]["content"][0]
        recorded_evidence_id = UUID(json.loads(last_tool_result["content"])["evidence_id"])
        return Message(
            id="msg_4",
            content=[TextBlock(text=_dossier_text(), type="text")],
            model=kwargs["model"],
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage=_usage(),
        )

    agent_runs = FakeAgentRunRepository()
    tool_calls = FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    output = await runtime.run(
        RESEARCH_AGENT_DEFINITION,
        input=ResearchAgentInput(
            company_id=company_id, company_name="Acme Rockets", company_domain="acme.example.com"
        ),
    )

    assert isinstance(output, ResearchDossier)
    fact_claims = [claim for claim in output.claims if claim.claim_type == ClaimType.FACT]
    assert fact_claims, "the dossier must contain at least one FACT claim"
    for claim in fact_claims:
        assert claim.evidence_ids, "every FACT claim must cite at least one evidence_id"
        for evidence_id in claim.evidence_ids:
            assert evidence_id in evidence_repo.rows, (
                "every cited evidence_id must correspond to a row actually recorded "
                "through record_evidence"
            )

    (run,) = agent_runs.runs.values()
    assert run.status == AgentRunStatus.COMPLETED
    assert len(tool_calls.calls) == 3
    assert {call.tool_name for call in tool_calls.calls.values()} == {
        "search_web",
        "fetch_page",
        "record_evidence",
    }
