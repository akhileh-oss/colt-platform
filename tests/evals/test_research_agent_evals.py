"""`ResearchAgent`'s golden evaluation suite (CLAUDE.md §2.6, §45.5, §68, Milestone 23).

Covers this milestone's **evidence-grounding tests** Build item. `DossierClaim`'s own pydantic
validator already makes an evidence-less `FACT` claim structurally impossible
(`test_colt_agents_research_agent.py` proves that), but it cannot catch a *fabricated* citation —
a well-formed `UUID` the model names that was never actually produced by a real
`record_evidence` tool call during the same run. That is the literal "hallucination rate" gap
this suite closes: one golden case cites real, recorded evidence (grounded); a second
deliberately cites a fabricated id the run never recorded (not grounded) — proving
`colt_agents.evals.grounding.check_evidence_grounding` catches exactly the failure mode the
dossier schema itself cannot.

Hermetic throughout: the same fake search/fetch providers, in-memory `EvidenceRepository`, and
faked `.messages.create` pattern `test_colt_agents_research_agent.py` already establishes.
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
from pydantic import SecretStr

from colt_agents.evals.grounding import check_evidence_grounding
from colt_agents.evals.report import EvalCaseOutcome, EvalReport, build_cost_report
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
from colt_domain import AgentRun, Evidence, ToolCall, VerificationStatus
from colt_integrations.fetch.port import FetchedDocument
from colt_integrations.search.fake import FakeSearchProvider
from colt_integrations.search.port import SearchResult

pytestmark = pytest.mark.evals

_SEARCH_URL = "https://news.example.com/acme-series-b"


class _FakeFetchProvider:
    def __init__(self, documents: dict[str, FetchedDocument]) -> None:
        self._documents = documents

    async def fetch(self, url: str) -> FetchedDocument:
        return self._documents[url]


class _FakeEvidenceRepository:
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


class _FakeAgentRunRepository:
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


class _FakeToolCallRepository:
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


def _usage() -> AnthropicUsage:
    return AnthropicUsage(
        input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0
    )


def _gateway(fake_create: Any) -> AnthropicGateway:
    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    client.messages.create = fake_create  # type: ignore[method-assign]
    return AnthropicGateway(
        AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )


async def _run_research_case(
    *, cited_evidence_id_override: UUID | None
) -> tuple[ResearchDossier, set[UUID], AgentRun]:
    """Drives one golden case through the real search -> fetch -> record_evidence -> dossier
    loop. `cited_evidence_id_override`, when given, makes the final dossier cite that id instead
    of the one the run actually recorded — simulating a hallucinated citation.
    """
    company_id = uuid4()
    search_provider = FakeSearchProvider(
        {
            "Acme Rockets": [
                SearchResult(
                    title="Acme Rockets raises $20M Series B",
                    url=_SEARCH_URL,
                    snippet="Acme Rockets announced a $20M Series B today.",
                )
            ]
        }
    )
    fetch_provider = _FakeFetchProvider(
        {
            _SEARCH_URL: FetchedDocument(
                url=_SEARCH_URL,
                final_url=_SEARCH_URL,
                status_code=200,
                title="Acme Rockets raises $20M Series B",
                text="Acme Rockets today announced it has raised a $20M Series B round.",
                fetched_at=datetime.now(UTC),
            )
        }
    )
    evidence_repo = _FakeEvidenceRepository(uuid4())
    record_evidence = RecordEvidence(evidence_repo)

    registry = ToolRegistry()
    registry.register(build_search_web_tool(search_provider))
    registry.register(build_fetch_page_tool(fetch_provider))
    registry.register(build_record_evidence_tool(record_evidence))

    recorded_evidence_id: UUID | None = None

    def _dossier_text() -> str:
        assert recorded_evidence_id is not None
        cited = cited_evidence_id_override or recorded_evidence_id
        return ResearchDossier(
            company_id=company_id,
            summary="Acme Rockets recently raised a Series B round.",
            claims=[
                DossierClaim(
                    claim_type=ClaimType.FACT,
                    text="Acme Rockets raised a $20M Series B.",
                    evidence_ids=[cited],
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
                        id="toolu_2", input={"url": _SEARCH_URL}, name="fetch_page", type="tool_use"
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
                            "source_url": _SEARCH_URL,
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

    agent_runs = _FakeAgentRunRepository()
    tool_calls = _FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create), registry, agent_runs, tool_calls)

    output = await runtime.run(
        RESEARCH_AGENT_DEFINITION,
        input=ResearchAgentInput(
            company_id=company_id, company_name="Acme Rockets", company_domain="acme.example.com"
        ),
    )
    assert isinstance(output, ResearchDossier)
    (run,) = agent_runs.runs.values()
    return output, set(evidence_repo.rows), run


async def test_research_agent_golden_suite_catches_a_hallucinated_citation() -> None:
    outcomes: list[EvalCaseOutcome] = []
    agent_runs: list[AgentRun] = []

    grounded_dossier, recorded_ids, grounded_run = await _run_research_case(
        cited_evidence_id_override=None
    )
    grounded_cited_ids = {
        evidence_id for claim in grounded_dossier.claims for evidence_id in claim.evidence_ids
    }
    grounded_result = check_evidence_grounding(
        cited_ids=grounded_cited_ids, recorded_ids=recorded_ids
    )
    outcomes.append(
        EvalCaseOutcome(
            case_id="grounded_fact_claim",
            passed=grounded_result.grounded is True,
            detail=f"hallucinated_ids={grounded_result.hallucinated_ids}",
        )
    )
    agent_runs.append(grounded_run)

    fabricated_id = uuid4()
    hallucinating_dossier, recorded_ids_2, hallucinating_run = await _run_research_case(
        cited_evidence_id_override=fabricated_id
    )
    hallucinating_cited_ids = {
        evidence_id for claim in hallucinating_dossier.claims for evidence_id in claim.evidence_ids
    }
    hallucinating_result = check_evidence_grounding(
        cited_ids=hallucinating_cited_ids, recorded_ids=recorded_ids_2
    )
    # The point of this case: the dossier schema's own validator happily accepts a FACT claim
    # that cites *a* UUID - it has no way to know that UUID was never actually recorded. Only
    # the grounding check, comparing against what record_evidence really produced, catches it.
    outcomes.append(
        EvalCaseOutcome(
            case_id="hallucinated_citation_is_caught",
            passed=hallucinating_result.grounded is False
            and fabricated_id in hallucinating_result.hallucinated_ids,
            detail=f"hallucinated_ids={hallucinating_result.hallucinated_ids}",
        )
    )
    agent_runs.append(hallucinating_run)

    report = EvalReport(agent_name=RESEARCH_AGENT_DEFINITION.name, outcomes=outcomes)
    assert report.pass_rate == 1.0, report.failures

    (cost_row,) = build_cost_report(agent_runs)
    assert cost_row.run_count == 2
