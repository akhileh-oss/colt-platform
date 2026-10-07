"""Regression evaluation (CLAUDE.md §46, Milestone 23's "regression evaluations" Build item).

CLAUDE.md §46 gives the minimum acceptance list literally ("No regression in schema validity...
No unacceptable cost increase...") without a mechanism for comparing two runs — this module is
that mechanism: a `current` `EvalReport` compared against a `baseline` one, stored as the
golden suite's own checked-in JSON fixture (`tests/evals/baselines/*.json`) from the last run
everyone agreed was good. Finding a regression never means failing by diff count — a suite can
grow new cases the baseline never had — it means a case that genuinely passed before now fails,
or the suite's overall pass rate dropped.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from colt_agents.evals.report import EvalReport


class RegressionFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    detail: str


def compare_against_baseline(current: EvalReport, baseline: EvalReport) -> list[RegressionFinding]:
    """Every way `current` is worse than `baseline` — empty when there is none."""
    findings: list[RegressionFinding] = []
    baseline_by_case = {outcome.case_id: outcome for outcome in baseline.outcomes}

    for outcome in current.outcomes:
        prior = baseline_by_case.get(outcome.case_id)
        if prior is not None and prior.passed and not outcome.passed:
            findings.append(
                RegressionFinding(
                    kind="case_regressed",
                    detail=(
                        f"{outcome.case_id}: passed in the baseline, now fails ({outcome.detail})"
                    ),
                )
            )

    if current.pass_rate < baseline.pass_rate:
        findings.append(
            RegressionFinding(
                kind="pass_rate_decreased",
                detail=f"{baseline.pass_rate:.0%} -> {current.pass_rate:.0%}",
            )
        )

    return findings
