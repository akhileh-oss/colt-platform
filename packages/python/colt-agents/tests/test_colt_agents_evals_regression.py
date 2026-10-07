"""`colt_agents.evals.regression` (CLAUDE.md §46, §68, Milestone 23)."""

from __future__ import annotations

from colt_agents.evals.regression import compare_against_baseline
from colt_agents.evals.report import EvalCaseOutcome, EvalReport


def test_no_findings_when_current_matches_baseline() -> None:
    baseline = EvalReport(
        agent_name="scoring-agent",
        outcomes=[EvalCaseOutcome(case_id="a", passed=True, detail="ok")],
    )
    current = EvalReport(
        agent_name="scoring-agent",
        outcomes=[EvalCaseOutcome(case_id="a", passed=True, detail="ok")],
    )

    assert compare_against_baseline(current, baseline) == []


def test_a_case_that_passed_in_the_baseline_and_now_fails_is_a_regression() -> None:
    baseline = EvalReport(
        agent_name="scoring-agent",
        outcomes=[EvalCaseOutcome(case_id="a", passed=True, detail="ok")],
    )
    current = EvalReport(
        agent_name="scoring-agent",
        outcomes=[EvalCaseOutcome(case_id="a", passed=False, detail="schema invalid")],
    )

    findings = compare_against_baseline(current, baseline)

    assert len(findings) == 2
    assert {f.kind for f in findings} == {"case_regressed", "pass_rate_decreased"}


def test_a_case_that_already_failed_in_the_baseline_is_not_a_new_regression() -> None:
    baseline = EvalReport(
        agent_name="scoring-agent",
        outcomes=[EvalCaseOutcome(case_id="a", passed=False, detail="already broken")],
    )
    current = EvalReport(
        agent_name="scoring-agent",
        outcomes=[EvalCaseOutcome(case_id="a", passed=False, detail="still broken")],
    )

    assert compare_against_baseline(current, baseline) == []


def test_a_new_case_not_in_the_baseline_cannot_regress() -> None:
    baseline = EvalReport(agent_name="scoring-agent", outcomes=[])
    current = EvalReport(
        agent_name="scoring-agent",
        outcomes=[EvalCaseOutcome(case_id="new-case", passed=False, detail="new, failing")],
    )

    findings = compare_against_baseline(current, baseline)

    assert [f.kind for f in findings] == ["pass_rate_decreased"]
