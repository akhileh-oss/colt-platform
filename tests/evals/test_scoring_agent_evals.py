"""`ScoringAgent`'s golden evaluation suite (CLAUDE.md §45.5, §46, §68, Milestone 23).

Covers three of this milestone's Build items for one agent: **structured-output validation**
(a response that fails `ScoringAgentOutput`'s own schema must be caught as a scored failure, not
crash the suite), **scoring consistency** (the same input run twice must produce the same
`overall_score` — §45.5's own "scoring consistency" Evaluate item), and **regression
evaluations** (this suite's own `EvalReport` is compared against a stored baseline
(`tests/evals/baselines/scoring_agent.json`) from the last run everyone agreed was good — a case
that passed there and fails here is a regression, caught before release, not after).

Hermetic throughout: the same fake-repository-plus-faked-`.messages.create` pattern every other
agent's own test file in `colt-agents` already establishes (no real Anthropic key exists in this
environment — the Milestone 08 caveat carried into every agent-dependent milestone since).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from anthropic.types import Usage as AnthropicUsage
from pydantic import SecretStr

from colt_agents.errors import AgentOutputValidationError
from colt_agents.evals.regression import compare_against_baseline
from colt_agents.evals.report import EvalCaseOutcome, EvalReport, average_latency_seconds
from colt_agents.registry import ToolRegistry
from colt_agents.runtime import AgentRuntime
from colt_agents.scoring_agent import (
    SCORING_AGENT_DEFINITION,
    ScoringAgentInput,
    ScoringAgentOutput,
)
from colt_agents.tools import build_score_lead_tool
from colt_ai import AnthropicGateway
from colt_application.use_cases.score_lead import ScoreLead
from colt_config import AnthropicSettings
from colt_domain import AgentRun, Lead, LeadScore, LeadStatus, ToolCall

pytestmark = pytest.mark.evals

_BASELINE_PATH = Path(__file__).parent / "baselines" / "scoring_agent.json"


class _FakeLeadScoreRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, LeadScore] = {}

    async def add(self, **kwargs: Any) -> LeadScore:
        score = LeadScore(
            id=uuid4(), organization_id=uuid4(), created_at=datetime.now(UTC), **kwargs
        )
        self.rows[score.id] = score
        return score

    async def get(self, lead_score_id: UUID) -> LeadScore | None:
        return self.rows.get(lead_score_id)

    async def list_by_lead(self, lead_id: UUID) -> list[LeadScore]:
        return [s for s in self.rows.values() if s.lead_id == lead_id]


class _FakeLeadRepository:
    def __init__(self, lead: Lead) -> None:
        self.lead = lead

    async def get(self, lead_id: UUID) -> Lead | None:
        return self.lead if lead_id == self.lead.id else None

    async def update_status(self, lead_id: UUID, status: LeadStatus, *, at: datetime) -> Lead:
        self.lead = self.lead.with_status(status, at=at)
        return self.lead


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


def _gateway(fake_create: Any, settings: AnthropicSettings | None = None) -> AnthropicGateway:
    client = AsyncAnthropic(api_key="sk-ant-test-key-not-real")
    client.messages.create = fake_create  # type: ignore[method-assign]
    return AnthropicGateway(
        settings or AnthropicSettings(api_key=SecretStr("sk-ant-test-key-not-real")), client=client
    )


async def _run_scoring_case(
    *,
    icp_fit: float,
    signal_strength: float,
    timing: float,
    tool_scores: dict[str, float],
    final_text: str | None = None,
    prompt_version: str | None = None,
    settings: AnthropicSettings | None = None,
) -> tuple[ScoringAgentOutput | None, AgentRun]:
    """Drives one golden case through a fresh, isolated `AgentRuntime` — its own lead, repos,
    and fake transport — exactly the shape a production caller uses. `final_text`, when given,
    overrides the agent's final turn verbatim, letting a case inject a deliberately malformed
    response; this function returns `(None, run)` rather than raising when that response is
    correctly rejected, so a structured-output regression is a *scored* eval failure, not a
    crash of the whole suite.
    """
    lead = Lead(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        person_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    lead_scores = _FakeLeadScoreRepository()
    leads = _FakeLeadRepository(lead)
    registry = ToolRegistry()
    registry.register(build_score_lead_tool(ScoreLead(lead_scores, leads)))

    turn = 0

    async def fake_create(**kwargs: Any) -> Message:
        nonlocal turn
        turn += 1
        if turn == 1:
            return Message(
                id="msg_1",
                content=[
                    ToolUseBlock(
                        id="toolu_1",
                        input={"lead_id": str(lead.id), "icp_fit": icp_fit, **tool_scores},
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
        if final_text is not None:
            text = final_text
        else:
            last_tool_result = kwargs["messages"][-1]["content"][0]
            result = json.loads(last_tool_result["content"])
            text = ScoringAgentOutput(
                lead_score_id=UUID(result["lead_score_id"]),
                persona_fit=tool_scores["persona_fit"],
                model_assessment=tool_scores["model_assessment"],
                overall_score=result["overall_score"],
                reason_codes=result["reason_codes"],
                qualified=result["qualified"],
            ).model_dump_json()
        return Message(
            id="msg_2",
            content=[TextBlock(text=text, type="text")],
            model=kwargs["model"],
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            type="message",
            usage=_usage(),
        )

    agent_runs = _FakeAgentRunRepository()
    tool_calls = _FakeToolCallRepository(agent_runs.organization_id)
    runtime = AgentRuntime(_gateway(fake_create, settings), registry, agent_runs, tool_calls)

    try:
        output = await runtime.run(
            SCORING_AGENT_DEFINITION,
            input=ScoringAgentInput(
                lead_id=lead.id, icp_fit=icp_fit, signal_strength=signal_strength, timing=timing
            ),
            prompt_version=prompt_version,
        )
    except AgentOutputValidationError:
        (run,) = agent_runs.runs.values()
        return None, run

    assert isinstance(output, ScoringAgentOutput)
    (run,) = agent_runs.runs.values()
    return output, run


async def _build_report(
    *,
    prompt_version: str | None = None,
    settings: AnthropicSettings | None = None,
    second_consistency_model_assessment: float = 0.6,
) -> tuple[EvalReport, list[AgentRun]]:
    """Runs the full golden suite once. `second_consistency_model_assessment` lets a caller
    simulate a prompt change that broke scoring consistency (CLAUDE.md §45.5) — passing
    anything other than the first call's own `0.6` makes the `scoring_consistency` case fail,
    a real, end-to-end regression `colt_agents.evals.comparison.compare_reports` can then catch,
    not merely a synthetic one.
    """
    outcomes: list[EvalCaseOutcome] = []
    agent_runs: list[AgentRun] = []
    model_name: str | None = None

    high_fit_output, high_fit_run = await _run_scoring_case(
        icp_fit=0.9,
        signal_strength=0.9,
        timing=0.9,
        tool_scores={
            "persona_fit": 0.9,
            "signal_strength": 0.9,
            "timing": 0.9,
            "model_assessment": 0.9,
        },
        prompt_version=prompt_version,
        settings=settings,
    )
    model_name = high_fit_run.model_name
    assert high_fit_output is not None
    outcomes.append(
        EvalCaseOutcome(
            case_id="high_fit_qualifies",
            passed=high_fit_output.qualified is True,
            detail=f"qualified={high_fit_output.qualified}",
        )
    )
    agent_runs.append(high_fit_run)

    low_fit_output, low_fit_run = await _run_scoring_case(
        icp_fit=0.1,
        signal_strength=0.1,
        timing=0.1,
        tool_scores={
            "persona_fit": 0.1,
            "signal_strength": 0.1,
            "timing": 0.1,
            "model_assessment": 0.1,
        },
        prompt_version=prompt_version,
        settings=settings,
    )
    assert low_fit_output is not None
    outcomes.append(
        EvalCaseOutcome(
            case_id="low_fit_not_qualified",
            passed=low_fit_output.qualified is False,
            detail=f"qualified={low_fit_output.qualified}",
        )
    )
    agent_runs.append(low_fit_run)

    first_output, first_run = await _run_scoring_case(
        icp_fit=0.7,
        signal_strength=0.6,
        timing=0.5,
        tool_scores={
            "persona_fit": 0.6,
            "signal_strength": 0.6,
            "timing": 0.5,
            "model_assessment": 0.6,
        },
        prompt_version=prompt_version,
        settings=settings,
    )
    second_output, second_run = await _run_scoring_case(
        icp_fit=0.7,
        signal_strength=0.6,
        timing=0.5,
        tool_scores={
            "persona_fit": 0.6,
            "signal_strength": 0.6,
            "timing": 0.5,
            "model_assessment": second_consistency_model_assessment,
        },
        prompt_version=prompt_version,
        settings=settings,
    )
    assert first_output is not None
    assert second_output is not None
    consistent = first_output.overall_score == second_output.overall_score
    outcomes.append(
        EvalCaseOutcome(
            case_id="scoring_consistency",
            passed=consistent,
            detail=f"{first_output.overall_score} vs {second_output.overall_score}",
        )
    )
    agent_runs.extend([first_run, second_run])

    malformed_output, malformed_run = await _run_scoring_case(
        icp_fit=0.5,
        signal_strength=0.5,
        timing=0.5,
        tool_scores={
            "persona_fit": 0.5,
            "signal_strength": 0.5,
            "timing": 0.5,
            "model_assessment": 0.5,
        },
        final_text=json.dumps(
            {
                "lead_score_id": str(uuid4()),
                "persona_fit": 0.5,
                "model_assessment": 0.5,
                "overall_score": 0.5,
                "qualified": False,
                # "reason_codes" is deliberately omitted - the regression this case exists to
                # catch.
            }
        ),
        prompt_version=prompt_version,
        settings=settings,
    )
    outcomes.append(
        EvalCaseOutcome(
            case_id="malformed_output_is_rejected",
            passed=malformed_output is None,
            detail=(
                "AgentOutputValidationError raised, as expected"
                if malformed_output is None
                else "a malformed response (missing reason_codes) was wrongly accepted"
            ),
        )
    )
    agent_runs.append(malformed_run)

    return (
        EvalReport(
            agent_name=SCORING_AGENT_DEFINITION.name,
            prompt_version=prompt_version,
            model_name=model_name,
            outcomes=outcomes,
        ),
        agent_runs,
    )


async def test_scoring_agent_golden_suite_all_cases_pass() -> None:
    report, _ = await _build_report()

    assert report.pass_rate == 1.0, report.failures


async def test_scoring_agent_golden_suite_has_no_regression_against_the_stored_baseline() -> None:
    report, _ = await _build_report()
    baseline = EvalReport.model_validate_json(_BASELINE_PATH.read_text())

    findings = compare_against_baseline(report, baseline)

    assert findings == [], findings


async def test_scoring_agent_golden_suite_cost_and_latency_report() -> None:
    _, agent_runs = await _build_report()

    assert len(agent_runs) == 5  # 2 scored + 2 consistency + 1 failed malformed attempt
    assert average_latency_seconds(agent_runs) is not None
    assert sum(run.estimated_cost_usd or 0.0 for run in agent_runs) > 0.0
