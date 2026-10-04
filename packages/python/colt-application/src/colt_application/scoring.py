"""Deterministic lead scoring and qualification (CLAUDE.md §21, §12.7, Milestone 13) — the
hybrid score §21 requires: "Do not allow LLM-only lead scoring. Use a hybrid score."

`compute_overall_score()` is the exact weighted sum §21's example baseline gives, with the
weights as a named, versioned constant (`DEFAULT_SCORE_WEIGHTS`/`SCORE_MODEL_VERSION`) rather
than inlined numbers - "this weighting is configurable and must be versioned." `model_assessment`
is the one component a `ScoringAgent` run supplies through its own qualitative judgment (§12.7);
every other step here - the weighted sum, the reason codes, and the qualification decision - is
plain arithmetic over already-known numbers, exactly what the acceptance criterion means by
"reproducible from persisted inputs and rules": given the same five component scores and the
same `model_version`'s weights, anyone recomputes the same `overall_score` and reason codes.
"""

from __future__ import annotations

from colt_domain import LeadStatus

SCORE_MODEL_VERSION = "v1"

#: CLAUDE.md §21's example baseline, verbatim.
DEFAULT_SCORE_WEIGHTS: dict[str, float] = {
    "icp_fit": 0.30,
    "persona_fit": 0.20,
    "signal_strength": 0.20,
    "timing": 0.15,
    "model_assessment": 0.15,
}

#: Above this overall_score, a lead qualifies; at or below, it does not (§12.7: "Never allow
#: 'vibes' alone to determine qualification" - this single number, not the model, decides).
QUALIFICATION_THRESHOLD = 0.6

#: A component this low or high is called out by name in the reason codes (CLAUDE.md §10.8).
_WEAK_COMPONENT_THRESHOLD = 0.3
_STRONG_COMPONENT_THRESHOLD = 0.7


def compute_overall_score(
    *,
    icp_fit: float,
    persona_fit: float,
    signal_strength: float,
    timing: float,
    model_assessment: float,
    weights: dict[str, float] | None = None,
) -> float:
    weights = weights if weights is not None else DEFAULT_SCORE_WEIGHTS
    return (
        weights["icp_fit"] * icp_fit
        + weights["persona_fit"] * persona_fit
        + weights["signal_strength"] * signal_strength
        + weights["timing"] * timing
        + weights["model_assessment"] * model_assessment
    )


def determine_reason_codes(
    *,
    icp_fit: float,
    persona_fit: float,
    signal_strength: float,
    timing: float,
    overall_score: float,
    qualification_threshold: float = QUALIFICATION_THRESHOLD,
) -> list[str]:
    """Deterministic, reproducible from the same inputs every time - never the model's own
    free-text explanation."""
    codes: list[str] = []
    for name, value in (
        ("ICP_FIT", icp_fit),
        ("PERSONA_FIT", persona_fit),
        ("BUYING_SIGNAL", signal_strength),
        ("TIMING", timing),
    ):
        if value <= _WEAK_COMPONENT_THRESHOLD:
            codes.append(f"WEAK_{name}")
        elif value >= _STRONG_COMPONENT_THRESHOLD:
            codes.append(f"STRONG_{name}")
    codes.append(
        "MEETS_QUALIFICATION_THRESHOLD"
        if overall_score >= qualification_threshold
        else "BELOW_QUALIFICATION_THRESHOLD"
    )
    return codes


def determine_qualification(
    overall_score: float, *, threshold: float = QUALIFICATION_THRESHOLD
) -> LeadStatus:
    """Reuses `LeadStatus`'s existing closed values - scoring does not need a vocabulary of its
    own for an outcome the lead funnel already has a name for."""
    return LeadStatus.QUALIFIED if overall_score >= threshold else LeadStatus.NOT_QUALIFIED
