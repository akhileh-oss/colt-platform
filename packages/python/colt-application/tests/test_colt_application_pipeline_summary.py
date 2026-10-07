"""Deterministic pipeline summary (CLAUDE.md §68, Milestone 21)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from colt_application.pipeline_summary import summarize_pipeline
from colt_domain import Opportunity, PipelineStage

NOW = datetime.now(UTC)


def _opportunity(*, pipeline_stage: PipelineStage, estimated_value: float | None) -> Opportunity:
    return Opportunity(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        pipeline_stage=pipeline_stage,
        estimated_value=estimated_value,
        created_at=NOW,
        updated_at=NOW,
    )


def test_every_stage_is_present_even_with_no_opportunities() -> None:
    summaries = {s.stage: s for s in summarize_pipeline([])}
    assert set(summaries) == set(PipelineStage)
    assert all(s.count == 0 and s.total_value == 0.0 for s in summaries.values())


def test_counts_and_totals_per_stage() -> None:
    opportunities = [
        _opportunity(pipeline_stage=PipelineStage.QUALIFIED, estimated_value=1000.0),
        _opportunity(pipeline_stage=PipelineStage.QUALIFIED, estimated_value=2000.0),
        _opportunity(pipeline_stage=PipelineStage.WON, estimated_value=5000.0),
        _opportunity(pipeline_stage=PipelineStage.LOST, estimated_value=None),
    ]

    summaries = {s.stage: s for s in summarize_pipeline(opportunities)}

    assert summaries[PipelineStage.QUALIFIED].count == 2
    assert summaries[PipelineStage.QUALIFIED].total_value == 3000.0
    assert summaries[PipelineStage.WON].count == 1
    assert summaries[PipelineStage.WON].total_value == 5000.0
    assert summaries[PipelineStage.LOST].count == 1
    assert summaries[PipelineStage.LOST].total_value == 0.0
    assert summaries[PipelineStage.DISCOVERY].count == 0
