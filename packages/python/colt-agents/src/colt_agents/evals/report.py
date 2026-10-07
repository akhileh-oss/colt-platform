"""Evaluation case outcomes and reports (CLAUDE.md §45.5, §46, Milestone 23).

`EvalCaseOutcome`/`EvalReport` are deliberately small and JSON-serializable (`pydantic.BaseModel`,
not a plain dataclass, the same distinction `colt_application`'s `Row` dataclasses draw from its
pydantic domain entities): a report is a record meant to be written to disk as a stored baseline
and read back later by `regression.compare_against_baseline`, not just held in memory for one
test's assertions.

Cost and latency are never stored on the report itself — they are computed straight from the
`AgentRun` rows a golden suite's own run produces, through `colt_application.summarize_agent_cost`
/`summarize_model_performance` (Milestone 22's own aggregations, reused unchanged here): an eval
run is itself a source of real `AgentRun` rows, no different from a production one.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from colt_application import (
    AgentCostRow,
    ModelPerformanceRow,
    summarize_agent_cost,
    summarize_model_performance,
)
from colt_domain import AgentRun


class EvalCaseOutcome(BaseModel):
    """One golden case's verdict: did the agent's real behavior match what this case expects."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    passed: bool
    detail: str


class EvalReport(BaseModel):
    """One golden suite's run against one `(agent_name, prompt_version, model_name)` combination."""

    model_config = ConfigDict(frozen=True)

    agent_name: str
    prompt_version: str | None = None
    model_name: str | None = None
    outcomes: list[EvalCaseOutcome]

    @property
    def pass_rate(self) -> float:
        """1.0 for an empty suite — nothing failed, there was simply nothing to fail."""
        if not self.outcomes:
            return 1.0
        return sum(1 for outcome in self.outcomes if outcome.passed) / len(self.outcomes)

    @property
    def failures(self) -> list[EvalCaseOutcome]:
        return [outcome for outcome in self.outcomes if not outcome.passed]


def average_latency_seconds(agent_runs: list[AgentRun]) -> float | None:
    """Mean wall-clock duration of every completed run — `None` when nothing has finished yet,
    never a misleading `0.0`."""
    durations = [
        (run.completed_at - run.started_at).total_seconds()
        for run in agent_runs
        if run.completed_at is not None
    ]
    if not durations:
        return None
    return sum(durations) / len(durations)


def build_cost_report(agent_runs: list[AgentRun]) -> list[AgentCostRow]:
    return summarize_agent_cost(agent_runs)


def build_model_report(agent_runs: list[AgentRun]) -> list[ModelPerformanceRow]:
    return summarize_model_performance(agent_runs)
