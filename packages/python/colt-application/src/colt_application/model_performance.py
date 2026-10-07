"""Deterministic model-performance summary (CLAUDE.md §68, Milestone 22's "model performance"
Build item) — grouped by `AgentRun.model_name`, a run's completion/failure rate and average
cost, the comparison a model migration or prompt change needs before (and after) rollout.
"""

from __future__ import annotations

from dataclasses import dataclass

from colt_domain import AgentRun, AgentRunStatus


@dataclass(frozen=True, slots=True)
class ModelPerformanceRow:
    model_name: str
    run_count: int
    completed_count: int
    failed_count: int
    success_rate: float
    average_cost_usd: float | None


@dataclass(slots=True)
class _Bucket:
    run_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    cost_sum: float = 0.0
    cost_count: int = 0


def summarize_model_performance(agent_runs: list[AgentRun]) -> list[ModelPerformanceRow]:
    totals: dict[str, _Bucket] = {}
    for run in agent_runs:
        bucket = totals.setdefault(run.model_name, _Bucket())
        bucket.run_count += 1
        if run.status is AgentRunStatus.COMPLETED:
            bucket.completed_count += 1
        elif run.status is AgentRunStatus.FAILED:
            bucket.failed_count += 1
        if run.estimated_cost_usd is not None:
            bucket.cost_sum += run.estimated_cost_usd
            bucket.cost_count += 1

    rows = []
    for model_name, bucket in sorted(totals.items()):
        finished = bucket.completed_count + bucket.failed_count
        success_rate = bucket.completed_count / finished if finished else 0.0
        average_cost_usd = bucket.cost_sum / bucket.cost_count if bucket.cost_count else None
        rows.append(
            ModelPerformanceRow(
                model_name=model_name,
                run_count=bucket.run_count,
                completed_count=bucket.completed_count,
                failed_count=bucket.failed_count,
                success_rate=success_rate,
                average_cost_usd=average_cost_usd,
            )
        )
    return rows
