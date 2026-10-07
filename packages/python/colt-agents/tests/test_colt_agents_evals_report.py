"""`colt_agents.evals.report` (CLAUDE.md §45.5, §68, Milestone 23)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from colt_agents.evals.report import (
    EvalCaseOutcome,
    EvalReport,
    average_latency_seconds,
    build_cost_report,
    build_model_report,
)
from colt_domain import AgentRun, AgentRunStatus

NOW = datetime.now(UTC)


def _agent_run(
    *,
    model_name: str = "claude-opus-5",
    status: AgentRunStatus = AgentRunStatus.RUNNING,
    estimated_cost_usd: float | None = None,
    completed_at: datetime | None = None,
) -> AgentRun:
    return AgentRun(
        id=uuid4(),
        organization_id=uuid4(),
        agent_name="scoring-agent",
        agent_version="v1",
        model_name=model_name,
        input_hash="hash",
        started_at=NOW,
        completed_at=completed_at,
        status=status,
        estimated_cost_usd=estimated_cost_usd,
    )


def test_pass_rate_is_one_for_an_empty_suite() -> None:
    report = EvalReport(agent_name="scoring-agent", outcomes=[])

    assert report.pass_rate == 1.0
    assert report.failures == []


def test_pass_rate_reflects_passed_vs_failed_outcomes() -> None:
    report = EvalReport(
        agent_name="scoring-agent",
        outcomes=[
            EvalCaseOutcome(case_id="a", passed=True, detail="ok"),
            EvalCaseOutcome(case_id="b", passed=False, detail="bad"),
        ],
    )

    assert report.pass_rate == 0.5
    assert [outcome.case_id for outcome in report.failures] == ["b"]


def test_eval_report_round_trips_through_json() -> None:
    report = EvalReport(
        agent_name="scoring-agent",
        prompt_version="v1",
        model_name="claude-opus-5",
        outcomes=[EvalCaseOutcome(case_id="a", passed=True, detail="ok")],
    )

    reread = EvalReport.model_validate_json(report.model_dump_json())

    assert reread == report


def test_average_latency_is_none_when_nothing_has_completed() -> None:
    runs = [_agent_run(status=AgentRunStatus.RUNNING, completed_at=None)]

    assert average_latency_seconds(runs) is None


def test_average_latency_averages_only_completed_runs() -> None:
    runs = [
        _agent_run(status=AgentRunStatus.RUNNING, completed_at=None),
        _agent_run(status=AgentRunStatus.COMPLETED, completed_at=NOW + timedelta(seconds=2)),
        _agent_run(status=AgentRunStatus.COMPLETED, completed_at=NOW + timedelta(seconds=4)),
    ]

    assert average_latency_seconds(runs) == 3.0


def test_build_cost_report_reuses_milestone_22s_agent_cost_summary() -> None:
    runs = [
        _agent_run(estimated_cost_usd=0.01),
        _agent_run(estimated_cost_usd=0.02),
    ]

    (row,) = build_cost_report(runs)

    assert row.agent_name == "scoring-agent"
    assert row.total_cost_usd == 0.03


def test_build_model_report_reuses_milestone_22s_model_performance_summary() -> None:
    runs = [
        _agent_run(model_name="claude-opus-5", status=AgentRunStatus.COMPLETED),
        _agent_run(model_name="claude-opus-5", status=AgentRunStatus.FAILED),
    ]

    (row,) = build_model_report(runs)

    assert row.model_name == "claude-opus-5"
    assert row.completed_count == 1
    assert row.failed_count == 1
