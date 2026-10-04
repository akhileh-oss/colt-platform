"""Signal confidence, freshness, and ranking (CLAUDE.md §12.6, Milestone 12) — deterministic
business logic, not an LLM judgment call (§2.1).

`rank_signal()` is reproducible from the signal's own stored fields alone: `signal_type`
(weighted by commercial urgency — a funding round says more about "why now" than a routine
news mention), `confidence`, and freshness (an event from a year ago is a weaker "why now"
trigger than one from last week, mirroring `colt_application.research`'s source-freshness
logic). It is a pure function, not a persisted column — §10.5 names no `rank` field, and
nothing here needs re-deriving later the way a stored score would (that is Milestone 13's
`ScoringAgent` job for lead qualification, not this one's for a single signal).
"""

from __future__ import annotations

from datetime import datetime

#: Relative commercial urgency per `signal_type` (CLAUDE.md §10.5's example list). A type not
#: in this table (new types are expected over time, per `colt_domain.signal`'s own docstring)
#: falls back to `DEFAULT_SIGNAL_TYPE_WEIGHT` rather than raising - an unrecognised type is a
#: weaker, not an invalid, signal.
SIGNAL_TYPE_WEIGHTS: dict[str, float] = {
    "funding": 0.9,
    "acquisition": 0.9,
    "expansion": 0.8,
    "leadership_change": 0.7,
    "product_launch": 0.6,
    "job_hiring": 0.5,
    "technology_change": 0.5,
    "market_event": 0.4,
    "regulatory_event": 0.4,
    "news": 0.3,
    "website_change": 0.2,
}
DEFAULT_SIGNAL_TYPE_WEIGHT = 0.3

#: Used when a signal carries no `confidence` at all.
DEFAULT_SIGNAL_CONFIDENCE = 0.5

#: A "why now" event loses relevance faster than a general research claim (§19.2) - 90 days,
#: against `colt_application.research`'s 180-day default for business facts.
DEFAULT_SIGNAL_FRESHNESS_THRESHOLD_DAYS = 90

#: A stale signal is weaker, not worthless - it may still be the only evidence of a trend.
STALE_SIGNAL_DECAY_FACTOR = 0.3


def rank_signal(
    *,
    signal_type: str,
    confidence: float | None,
    event_at: datetime | None,
    observed_at: datetime,
    now: datetime,
    freshness_threshold_days: int = DEFAULT_SIGNAL_FRESHNESS_THRESHOLD_DAYS,
) -> float:
    """A 0-1 score combining type weight, confidence, and freshness decay.

    Prefers `event_at` (when the underlying event actually happened) over `observed_at` (when
    Colt noticed it) for freshness, the same preference `determine_verification_status` gives
    `source_date` over `observed_at`.
    """
    type_weight = SIGNAL_TYPE_WEIGHTS.get(signal_type, DEFAULT_SIGNAL_TYPE_WEIGHT)
    effective_confidence = confidence if confidence is not None else DEFAULT_SIGNAL_CONFIDENCE
    reference_at = event_at if event_at is not None else observed_at
    age_days = (now - reference_at).days
    freshness_factor = 1.0 if age_days <= freshness_threshold_days else STALE_SIGNAL_DECAY_FACTOR
    return type_weight * effective_confidence * freshness_factor
