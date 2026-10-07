"""Deterministic model-performance summary (CLAUDE.md §68, Milestone 22)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from colt_application.model_performance import summarize_model_performance
from colt_domain import AgentRun, AgentRunStatus

NOW = datetime.now(UTC)


def _agent_run(
    *,
    model_name: str,
    status: AgentRunStatus = AgentRunStatus.RUNNING,
    estimated_cost_usd: float | None = None,
) -> AgentRun:
    return AgentRun(
        id=uuid4(),
        organization_id=uuid4(),
        agent_name="ScoringAgent",
        agent_version="v1",
        model_name=model_name,
        input_hash="hash",
        started_at=NOW,
        status=status,
        estimated_cost_usd=estimated_cost_usd,
    )


def test_runs_group_by_model_name() -> None:
    runs = [
        _agent_run(model_name="claude-opus-5", status=AgentRunStatus.COMPLETED),
        _agent_run(model_name="claude-opus-5", status=AgentRunStatus.COMPLETED),
        _agent_run(model_name="claude-haiku-4-5", status=AgentRunStatus.COMPLETED),
    ]

    rows = {row.model_name: row for row in summarize_model_performance(runs)}

    assert rows["claude-opus-5"].run_count == 2
    assert rows["claude-haiku-4-5"].run_count == 1


def test_success_rate_is_completed_over_finished_runs() -> None:
    runs = [
        _agent_run(model_name="claude-opus-5", status=AgentRunStatus.COMPLETED),
        _agent_run(model_name="claude-opus-5", status=AgentRunStatus.COMPLETED),
        _agent_run(model_name="claude-opus-5", status=AgentRunStatus.FAILED),
    ]

    rows = summarize_model_performance(runs)

    assert rows[0].completed_count == 2
    assert rows[0].failed_count == 1
    assert rows[0].success_rate == 2 / 3


def test_still_running_runs_count_toward_run_count_but_not_success_rate() -> None:
    runs = [
        _agent_run(model_name="claude-opus-5", status=AgentRunStatus.RUNNING),
        _agent_run(model_name="claude-opus-5", status=AgentRunStatus.COMPLETED),
    ]

    rows = summarize_model_performance(runs)

    assert rows[0].run_count == 2
    assert rows[0].success_rate == 1.0


def test_success_rate_is_zero_when_no_run_has_finished() -> None:
    runs = [_agent_run(model_name="claude-opus-5", status=AgentRunStatus.RUNNING)]

    rows = summarize_model_performance(runs)

    assert rows[0].success_rate == 0.0


def test_average_cost_ignores_runs_with_no_recorded_cost() -> None:
    runs = [
        _agent_run(model_name="claude-opus-5", estimated_cost_usd=0.10),
        _agent_run(model_name="claude-opus-5", estimated_cost_usd=None),
    ]

    rows = summarize_model_performance(runs)

    assert rows[0].average_cost_usd == 0.10


def test_average_cost_is_none_when_no_run_carries_one() -> None:
    runs = [_agent_run(model_name="claude-opus-5", estimated_cost_usd=None)]

    rows = summarize_model_performance(runs)

    assert rows[0].average_cost_usd is None
