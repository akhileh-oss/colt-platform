"""Prompt and model comparison reports (CLAUDE.md §46, §68, Milestone 23) — the literal
mechanism behind this milestone's acceptance criterion, "prompt/model changes can be evaluated
before release."

Both reuse `ScoringAgent`'s own golden suite (`test_scoring_agent_evals._build_report`), run
twice and diffed with `colt_agents.evals.comparison.compare_reports`:

- **Model comparison**: the exact same scripted responses, run once under each of two
  `AnthropicSettings.model_fast` overrides (`ScoringAgent` routes through `ModelClass.FAST`,
  CLAUDE.md §14.1) — `claude-haiku-4-5` vs `claude-opus-5` — no real
  model call happens either way (no real Anthropic key exists in this environment, the
  Milestone 08 caveat carried into every agent-dependent milestone since), but the *cost*
  difference is real: `colt_ai.pricing.estimate_cost_usd` prices both models for real, so the
  comparison report's cost delta is the real production number a model-routing change would
  actually produce, not a stand-in.
- **Prompt comparison**: run twice with a different `prompt_version` label, with
  `second_consistency_model_assessment` deliberately varied between the two runs — simulating a
  prompt change that broke `scoring_consistency` (CLAUDE.md §45.5). This is a documented,
  test-controlled simulation (there is no real prompt text to actually change the model's
  behavior here), but every other part of the path — `AgentRuntime`, `EvalReport`,
  `compare_against_baseline` — runs for real, so the comparison genuinely catches the real
  regression this simulation introduces.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from colt_agents.evals.comparison import ComparisonDimension, compare_reports
from colt_config import AnthropicSettings
from evals.test_scoring_agent_evals import _build_report

pytestmark = pytest.mark.evals


async def test_model_comparison_report_shows_a_real_cost_difference() -> None:
    # ScoringAgent routes through ModelClass.FAST (CLAUDE.md §14.1) - override model_fast, the
    # field its gateway.model_for() call actually resolves, not model_standard.
    haiku_settings = AnthropicSettings(
        api_key=SecretStr("sk-ant-test-key-not-real"), model_fast="claude-haiku-4-5"
    )
    opus_settings = AnthropicSettings(
        api_key=SecretStr("sk-ant-test-key-not-real"), model_fast="claude-opus-5"
    )

    haiku_report, haiku_runs = await _build_report(settings=haiku_settings)
    opus_report, opus_runs = await _build_report(settings=opus_settings)

    comparison = compare_reports(
        dimension=ComparisonDimension.MODEL_NAME,
        baseline=haiku_report,
        baseline_agent_runs=haiku_runs,
        candidate=opus_report,
        candidate_agent_runs=opus_runs,
    )

    assert comparison.baseline_label == "claude-haiku-4-5"
    assert comparison.candidate_label == "claude-opus-5"
    # Same scripted behavior either way - no regression from switching models alone.
    assert comparison.baseline_pass_rate == comparison.candidate_pass_rate == 1.0
    assert comparison.regressions == []
    # But opus is real-priced more expensive than haiku per colt_ai.pricing - a genuine cost
    # delta a model-routing change before release needs to see.
    assert comparison.candidate_total_cost_usd > comparison.baseline_total_cost_usd


async def test_prompt_comparison_report_catches_a_simulated_consistency_regression() -> None:
    baseline_report, baseline_runs = await _build_report(
        prompt_version="v1", second_consistency_model_assessment=0.6
    )
    # The "v2" prompt is simulated to produce a different model_assessment on the second,
    # otherwise-identical consistency-check call - breaking CLAUDE.md §45.5's scoring
    # consistency, exactly the kind of regression a prompt change must be caught before release.
    candidate_report, candidate_runs = await _build_report(
        prompt_version="v2", second_consistency_model_assessment=0.4
    )

    comparison = compare_reports(
        dimension=ComparisonDimension.PROMPT_VERSION,
        baseline=baseline_report,
        baseline_agent_runs=baseline_runs,
        candidate=candidate_report,
        candidate_agent_runs=candidate_runs,
    )

    assert comparison.baseline_label == "v1"
    assert comparison.candidate_label == "v2"
    assert comparison.baseline_pass_rate == 1.0
    assert comparison.candidate_pass_rate < 1.0
    regression_kinds = {finding.kind for finding in comparison.regressions}
    assert "case_regressed" in regression_kinds
    assert "pass_rate_decreased" in regression_kinds
