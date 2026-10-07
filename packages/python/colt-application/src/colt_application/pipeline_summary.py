"""Deterministic pipeline summary (CLAUDE.md §68, Milestone 21's "pipeline dashboard" Build
item) — per-stage counts and open value, a pure function of `Opportunity` rows the dashboard's
read endpoint computes on every request rather than maintaining a separate materialized total
that could drift from the rows it describes.
"""

from __future__ import annotations

from dataclasses import dataclass

from colt_domain import Opportunity, PipelineStage


@dataclass(frozen=True, slots=True)
class PipelineStageSummary:
    stage: PipelineStage
    count: int
    total_value: float


@dataclass(slots=True)
class _Bucket:
    count: int = 0
    total: float = 0.0


def summarize_pipeline(opportunities: list[Opportunity]) -> list[PipelineStageSummary]:
    totals: dict[PipelineStage, _Bucket] = {stage: _Bucket() for stage in PipelineStage}
    for opportunity in opportunities:
        bucket = totals[opportunity.pipeline_stage]
        bucket.count += 1
        bucket.total += opportunity.estimated_value or 0.0

    return [
        PipelineStageSummary(stage=stage, count=bucket.count, total_value=bucket.total)
        for stage, bucket in totals.items()
    ]
