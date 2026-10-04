from __future__ import annotations

from colt_application.scoring import (
    QUALIFICATION_THRESHOLD,
    compute_overall_score,
    determine_qualification,
    determine_reason_codes,
)
from colt_domain import LeadStatus


def test_compute_overall_score_matches_the_claude_md_21_baseline_weights() -> None:
    score = compute_overall_score(
        icp_fit=1.0, persona_fit=1.0, signal_strength=1.0, timing=1.0, model_assessment=1.0
    )
    assert score == 1.0

    score = compute_overall_score(
        icp_fit=1.0, persona_fit=0.0, signal_strength=0.0, timing=0.0, model_assessment=0.0
    )
    assert score == 0.30


def test_compute_overall_score_is_reproducible_from_the_same_inputs() -> None:
    first = compute_overall_score(
        icp_fit=0.8, persona_fit=0.6, signal_strength=0.7, timing=0.5, model_assessment=0.4
    )
    second = compute_overall_score(
        icp_fit=0.8, persona_fit=0.6, signal_strength=0.7, timing=0.5, model_assessment=0.4
    )
    assert first == second


def test_determine_reason_codes_flags_weak_and_strong_components() -> None:
    codes = determine_reason_codes(
        icp_fit=0.9, persona_fit=0.1, signal_strength=0.5, timing=0.8, overall_score=0.5
    )
    assert "STRONG_ICP_FIT" in codes
    assert "WEAK_PERSONA_FIT" in codes
    assert "STRONG_TIMING" in codes
    assert not any(code.endswith("BUYING_SIGNAL") for code in codes)


def test_determine_reason_codes_always_includes_the_qualification_outcome() -> None:
    above = determine_reason_codes(
        icp_fit=0.5, persona_fit=0.5, signal_strength=0.5, timing=0.5, overall_score=0.9
    )
    below = determine_reason_codes(
        icp_fit=0.5, persona_fit=0.5, signal_strength=0.5, timing=0.5, overall_score=0.1
    )
    assert "MEETS_QUALIFICATION_THRESHOLD" in above
    assert "BELOW_QUALIFICATION_THRESHOLD" in below


def test_determine_qualification_is_a_sharp_threshold() -> None:
    assert determine_qualification(QUALIFICATION_THRESHOLD) == LeadStatus.QUALIFIED
    assert determine_qualification(QUALIFICATION_THRESHOLD - 0.01) == LeadStatus.NOT_QUALIFIED
    assert determine_qualification(1.0) == LeadStatus.QUALIFIED
    assert determine_qualification(0.0) == LeadStatus.NOT_QUALIFIED
