"""The AI evaluation system (CLAUDE.md §45.5, §46, §68, Milestone 23).

Pure, I/O-free analysis of a golden suite's own results — never a new agent, never a new
production code path. A golden suite itself (`tests/evals/test_*.py`) drives the real
`AgentRuntime` against a fixed set of golden cases exactly the way a production caller would,
then hands this package's functions the resulting `EvalCaseOutcome`s and `AgentRun` rows.
"""

from colt_agents.evals.comparison import ComparisonDimension, ComparisonReport, compare_reports
from colt_agents.evals.grounding import GroundingResult, check_evidence_grounding
from colt_agents.evals.regression import RegressionFinding, compare_against_baseline
from colt_agents.evals.report import (
    EvalCaseOutcome,
    EvalReport,
    average_latency_seconds,
    build_cost_report,
    build_model_report,
)

__all__ = [
    "ComparisonDimension",
    "ComparisonReport",
    "EvalCaseOutcome",
    "EvalReport",
    "GroundingResult",
    "RegressionFinding",
    "average_latency_seconds",
    "build_cost_report",
    "build_model_report",
    "check_evidence_grounding",
    "compare_against_baseline",
    "compare_reports",
]
