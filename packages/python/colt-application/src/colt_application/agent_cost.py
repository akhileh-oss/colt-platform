"""Deterministic agent-cost summary (CLAUDE.md §68, §82, Milestone 22's "agent cost" Build
item) — grouped by `AgentRun.agent_name`, summing the exact cost/token fields `AgentRuntime`
already records on every run (§10.15), never re-estimated.
"""

from __future__ import annotations

from dataclasses import dataclass

from colt_domain import AgentRun


@dataclass(frozen=True, slots=True)
class AgentCostRow:
    agent_name: str
    run_count: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_tool_tokens: int


@dataclass(slots=True)
class _Bucket:
    run_count: int = 0
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tool_tokens: int = 0


def summarize_agent_cost(agent_runs: list[AgentRun]) -> list[AgentCostRow]:
    totals: dict[str, _Bucket] = {}
    for run in agent_runs:
        bucket = totals.setdefault(run.agent_name, _Bucket())
        bucket.run_count += 1
        bucket.total_cost_usd += run.estimated_cost_usd or 0.0
        bucket.total_input_tokens += run.input_tokens
        bucket.total_output_tokens += run.output_tokens
        bucket.total_tool_tokens += run.tool_tokens

    return [
        AgentCostRow(
            agent_name=agent_name,
            run_count=bucket.run_count,
            total_cost_usd=bucket.total_cost_usd,
            total_input_tokens=bucket.total_input_tokens,
            total_output_tokens=bucket.total_output_tokens,
            total_tool_tokens=bucket.total_tool_tokens,
        )
        for agent_name, bucket in sorted(totals.items())
    ]
