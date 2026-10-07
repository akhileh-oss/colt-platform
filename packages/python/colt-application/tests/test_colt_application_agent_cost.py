"""Deterministic agent-cost summary (CLAUDE.md §68, §82, Milestone 22)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from colt_application.agent_cost import summarize_agent_cost
from colt_domain import AgentRun

NOW = datetime.now(UTC)


def _agent_run(
    *,
    agent_name: str,
    estimated_cost_usd: float | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    tool_tokens: int = 0,
) -> AgentRun:
    return AgentRun(
        id=uuid4(),
        organization_id=uuid4(),
        agent_name=agent_name,
        agent_version="v1",
        model_name="claude-opus-5",
        input_hash="hash",
        started_at=NOW,
        estimated_cost_usd=estimated_cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_tokens=tool_tokens,
    )


def test_runs_group_by_agent_name() -> None:
    runs = [
        _agent_run(agent_name="ScoringAgent", estimated_cost_usd=0.01),
        _agent_run(agent_name="ScoringAgent", estimated_cost_usd=0.02),
        _agent_run(agent_name="SignalAgent", estimated_cost_usd=0.03),
    ]

    rows = {row.agent_name: row for row in summarize_agent_cost(runs)}

    assert rows["ScoringAgent"].run_count == 2
    assert rows["ScoringAgent"].total_cost_usd == 0.03
    assert rows["SignalAgent"].run_count == 1


def test_runs_with_no_recorded_cost_contribute_zero() -> None:
    runs = [_agent_run(agent_name="ScoringAgent", estimated_cost_usd=None)]

    rows = summarize_agent_cost(runs)

    assert rows[0].total_cost_usd == 0.0


def test_sums_token_counts() -> None:
    runs = [
        _agent_run(agent_name="ScoringAgent", input_tokens=100, output_tokens=50, tool_tokens=10),
        _agent_run(agent_name="ScoringAgent", input_tokens=200, output_tokens=75, tool_tokens=5),
    ]

    rows = summarize_agent_cost(runs)

    assert rows[0].total_input_tokens == 300
    assert rows[0].total_output_tokens == 125
    assert rows[0].total_tool_tokens == 15


def test_rows_are_sorted_by_agent_name() -> None:
    runs = [_agent_run(agent_name="SignalAgent"), _agent_run(agent_name="ScoringAgent")]

    rows = summarize_agent_cost(runs)

    assert [row.agent_name for row in rows] == ["ScoringAgent", "SignalAgent"]


def test_no_runs_returns_an_empty_list() -> None:
    assert summarize_agent_cost([]) == []
