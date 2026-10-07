"""Deterministic revenue attribution (CLAUDE.md §68, Milestone 21's "revenue attribution" Build
item). CLAUDE.md names the item without specifying a mechanism — grouping closed-won
`Opportunity` rows by their own `source` field (already recorded, e.g. `"conversation"` for
`CreateOrUpdateOpportunity`'s own callers) is this milestone's own documented, minimal design
decision, the same "the milestone building it makes the documented call" pattern
`CampaignStatus`/`Urgency` already establish. A pure function of already-stored fields, like
`colt_application.signals.rank_signal` — not a persisted column, reproducible from the
`Opportunity` rows themselves.

Grouped by `(source, currency)`, not `source` alone: summing different currencies into one
number would be meaningless. This environment does not convert between currencies (CLAUDE.md
specifies no exchange-rate mechanism) — a documented simplification, not an oversight.
"""

from __future__ import annotations

from dataclasses import dataclass

from colt_domain import Opportunity, PipelineStage

_UNKNOWN_SOURCE = "unknown"


@dataclass(frozen=True, slots=True)
class RevenueAttributionRow:
    source: str
    currency: str | None
    total_value: float
    opportunity_count: int
    includes_estimate: bool


@dataclass(slots=True)
class _Bucket:
    total: float = 0.0
    count: int = 0
    includes_estimate: bool = False


def summarize_revenue_by_source(opportunities: list[Opportunity]) -> list[RevenueAttributionRow]:
    """Closed-won revenue only — a pipeline still in flight has no revenue to attribute yet."""
    totals: dict[tuple[str, str | None], _Bucket] = {}
    for opportunity in opportunities:
        if opportunity.pipeline_stage is not PipelineStage.WON:
            continue
        key = (opportunity.source or _UNKNOWN_SOURCE, opportunity.currency)
        bucket = totals.setdefault(key, _Bucket())
        bucket.total += opportunity.estimated_value or 0.0
        bucket.count += 1
        bucket.includes_estimate = bucket.includes_estimate or opportunity.is_estimated_value

    def _sort_key(item: tuple[tuple[str, str | None], _Bucket]) -> tuple[str, str]:
        (source, currency), _ = item
        return (source, currency or "")

    return [
        RevenueAttributionRow(
            source=source,
            currency=currency,
            total_value=bucket.total,
            opportunity_count=bucket.count,
            includes_estimate=bucket.includes_estimate,
        )
        for (source, currency), bucket in sorted(totals.items(), key=_sort_key)
    ]
