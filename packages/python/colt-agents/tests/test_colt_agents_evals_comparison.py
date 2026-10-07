"""`colt_agents.evals.comparison` (CLAUDE.md §46, §68, Milestone 23)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from colt_agents.evals.comparison import ComparisonDimension, compare_reports
from colt_agents.evals.report import EvalCaseOutcome, EvalReport
from colt_domain import AgentRun

NOW = datetime.now(UTC)


def _agent_run(*, model_name: str, estimated_cost_usd: float | None) -> AgentRun:
    return AgentRun(
        id=uuid4(),
        organization_id=uuid4(),
        agent_name="scoring-agent",
        agent_version="v1",
        model_name=model_name,
        input_hash="hash",
        started_at=NOW,
        estimated_cost_usd=estimated_cost_usd,
    )


def test_prompt_comparison_reports_both_labels_and_pass_rates() -> None:
    baseline = EvalReport(
        agent_name="scoring-agent",
        prompt_version="v1",
        outcomes=[EvalCaseOutcome(case_id="a", passed=True, detail="ok")],
    )
    candidate = EvalReport(
        agent_name="scoring-agent",
        prompt_version="v2",
        outcomes=[EvalCaseOutcome(case_id="a", passed=False, detail="regressed under v2")],
    )
    baseline_runs = [_agent_run(model_name="claude-opus-5", estimated_cost_usd=0.01)]
    candidate_runs = [_agent_run(model_name="claude-opus-5", estimated_cost_usd=0.01)]

    report = compare_reports(
        dimension=ComparisonDimension.PROMPT_VERSION,
        baseline=baseline,
        baseline_agent_runs=baseline_runs,
        candidate=candidate,
        candidate_agent_runs=candidate_runs,
    )

    assert report.baseline_label == "v1"
    assert report.candidate_label == "v2"
    assert report.baseline_pass_rate == 1.0
    assert report.candidate_pass_rate == 0.0
    assert len(report.regressions) == 2


def test_model_comparison_reports_cost_difference() -> None:
    baseline = EvalReport(
        agent_name="scoring-agent",
        model_name="claude-haiku-4-5",
        outcomes=[EvalCaseOutcome(case_id="a", passed=True, detail="ok")],
    )
    candidate = EvalReport(
        agent_name="scoring-agent",
        model_name="claude-opus-5",
        outcomes=[EvalCaseOutcome(case_id="a", passed=True, detail="ok")],
    )
    baseline_runs = [_agent_run(model_name="claude-haiku-4-5", estimated_cost_usd=0.001)]
    candidate_runs = [_agent_run(model_name="claude-opus-5", estimated_cost_usd=0.05)]

    report = compare_reports(
        dimension=ComparisonDimension.MODEL_NAME,
        baseline=baseline,
        baseline_agent_runs=baseline_runs,
        candidate=candidate,
        candidate_agent_runs=candidate_runs,
    )

    assert report.baseline_label == "claude-haiku-4-5"
    assert report.candidate_label == "claude-opus-5"
    assert report.candidate_total_cost_usd > report.baseline_total_cost_usd
    assert report.regressions == []


def test_total_cost_treats_a_missing_estimate_as_zero() -> None:
    report = EvalReport(agent_name="scoring-agent", outcomes=[])
    runs = [_agent_run(model_name="claude-opus-5", estimated_cost_usd=None)]

    compared = compare_reports(
        dimension=ComparisonDimension.MODEL_NAME,
        baseline=report,
        baseline_agent_runs=runs,
        candidate=report,
        candidate_agent_runs=runs,
    )

    assert compared.baseline_total_cost_usd == 0.0
