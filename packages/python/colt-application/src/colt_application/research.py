"""Source verification (CLAUDE.md §20, §19.2) — deterministic business logic, not an LLM
judgment call (§2.1: "Application services = deterministic business logic").

This milestone's verification rule is deliberately narrow: it can demote a claim to `STALE`
(§19.2: "do not present stale information as current"), but it cannot promote one to `VERIFIED`,
`DISPUTED` or `REJECTED` — those require either independent corroboration or human review,
neither of which exists yet. A freshly observed, single-source claim from an automated agent
starts `UNVERIFIED` and stays there until a later milestone builds one of those mechanisms; §20
is explicit that `UNVERIFIED` evidence may inform research but must not be presented as fact in
outbound messaging, so leaving it there by default is the safe side to default to, not a gap.
"""

from __future__ import annotations

from datetime import date, datetime

from colt_domain import VerificationStatus

#: How old a source can be before a claim about it is presented as current (§19.2). 180 days is
#: a deliberately conservative default for business facts (headcount, funding, leadership) —
#: configurable per call rather than per environment, since freshness tolerance is a property of
#: the claim being made, not of where the code runs.
DEFAULT_FRESHNESS_THRESHOLD_DAYS = 180


def determine_verification_status(
    *,
    source_date: date | None,
    observed_at: datetime,
    now: datetime,
    freshness_threshold_days: int = DEFAULT_FRESHNESS_THRESHOLD_DAYS,
) -> VerificationStatus:
    """`STALE` if the claim's source is older than the freshness threshold, else `UNVERIFIED`.

    Prefers `source_date` (when the fact was actually true) over `observed_at` (when Colt
    noticed it) — a claim observed today about an event from a year ago is stale regardless of
    how recently it was fetched.
    """
    reference_date = source_date if source_date is not None else observed_at.date()
    age_days = (now.date() - reference_date).days
    if age_days > freshness_threshold_days:
        return VerificationStatus.STALE
    return VerificationStatus.UNVERIFIED
