"""Prompt and model comparison reports (CLAUDE.md §46, Milestone 23's "prompt comparison
reports"/"model comparison reports" Build items) — the literal mechanism behind this
milestone's acceptance criterion, "prompt/model changes can be evaluated before release."

Both Build items are the same comparison along a different axis of the same `EvalReport`: run
one golden suite twice — once with a prompt change, once with a model change, never both in the
same comparison — and diff the two reports. `ComparisonDimension` names which axis changed, so
the one `compare_reports` function serves both Build items rather than two near-duplicates.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from colt_agents.evals.regression import RegressionFinding, compare_against_baseline
from colt_agents.evals.report import EvalReport
from colt_domain import AgentRun


class ComparisonDimension(StrEnum):
    PROMPT_VERSION = "prompt_version"
    MODEL_NAME = "model_name"


class ComparisonReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: ComparisonDimension
    baseline_label: str | None
    candidate_label: str | None
    baseline_pass_rate: float
    candidate_pass_rate: float
    baseline_total_cost_usd: float
    candidate_total_cost_usd: float
    regressions: list[RegressionFinding]


def _total_cost_usd(agent_runs: list[AgentRun]) -> float:
    return sum(run.estimated_cost_usd or 0.0 for run in agent_runs)


def _label(report: EvalReport, dimension: ComparisonDimension) -> str | None:
    return (
        report.prompt_version
        if dimension is ComparisonDimension.PROMPT_VERSION
        else report.model_name
    )


def compare_reports(
    *,
    dimension: ComparisonDimension,
    baseline: EvalReport,
    baseline_agent_runs: list[AgentRun],
    candidate: EvalReport,
    candidate_agent_runs: list[AgentRun],
) -> ComparisonReport:
    return ComparisonReport(
        dimension=dimension,
        baseline_label=_label(baseline, dimension),
        candidate_label=_label(candidate, dimension),
        baseline_pass_rate=baseline.pass_rate,
        candidate_pass_rate=candidate.pass_rate,
        baseline_total_cost_usd=_total_cost_usd(baseline_agent_runs),
        candidate_total_cost_usd=_total_cost_usd(candidate_agent_runs),
        regressions=compare_against_baseline(candidate, baseline),
    )
