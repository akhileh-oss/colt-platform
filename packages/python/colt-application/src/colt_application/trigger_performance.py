"""Deterministic trigger (signal) performance summary (CLAUDE.md §68, Milestone 22's "trigger
performance" Build item) — grouped by `Signal.signal_type` (an open vocabulary, §12.6), with
each signal type's real commercial outcome: of the companies that ever had a signal of this
type, how many went on to a closed-won `Opportunity`. Answers the acceptance criterion's "what
... signals ... produce commercial outcomes" directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from colt_domain import Opportunity, PipelineStage, Signal


@dataclass(frozen=True, slots=True)
class TriggerPerformanceRow:
    signal_type: str
    signal_count: int
    company_count: int
    won_company_count: int
    average_confidence: float | None


@dataclass(slots=True)
class _Bucket:
    signal_count: int = 0
    companies: set[UUID] = field(default_factory=set)
    confidence_sum: float = 0.0
    confidence_count: int = 0


def summarize_trigger_performance(
    signals: list[Signal], opportunities: list[Opportunity]
) -> list[TriggerPerformanceRow]:
    won_companies = {o.company_id for o in opportunities if o.pipeline_stage is PipelineStage.WON}

    totals: dict[str, _Bucket] = {}
    for signal in signals:
        bucket = totals.setdefault(signal.signal_type, _Bucket())
        bucket.signal_count += 1
        bucket.companies.add(signal.company_id)
        if signal.confidence is not None:
            bucket.confidence_sum += signal.confidence
            bucket.confidence_count += 1

    rows = []
    for signal_type, bucket in sorted(totals.items()):
        average_confidence = (
            bucket.confidence_sum / bucket.confidence_count if bucket.confidence_count else None
        )
        rows.append(
            TriggerPerformanceRow(
                signal_type=signal_type,
                signal_count=bucket.signal_count,
                company_count=len(bucket.companies),
                won_company_count=len(bucket.companies & won_companies),
                average_confidence=average_confidence,
            )
        )
    return rows
