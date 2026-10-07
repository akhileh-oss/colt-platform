"""Deterministic revenue attribution (CLAUDE.md §68, Milestone 21)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from colt_application.revenue_attribution import summarize_revenue_by_source
from colt_domain import Opportunity, PipelineStage

NOW = datetime.now(UTC)


def _opportunity(
    *,
    pipeline_stage: PipelineStage,
    source: str | None,
    estimated_value: float | None,
    currency: str | None,
    is_estimated_value: bool = False,
) -> Opportunity:
    return Opportunity(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        pipeline_stage=pipeline_stage,
        source=source,
        estimated_value=estimated_value,
        currency=currency,
        is_estimated_value=is_estimated_value,
        created_at=NOW,
        updated_at=NOW,
    )


def test_only_won_opportunities_are_attributed() -> None:
    opportunities = [
        _opportunity(
            pipeline_stage=PipelineStage.NEGOTIATION,
            source="conversation",
            estimated_value=5000.0,
            currency="USD",
        ),
        _opportunity(
            pipeline_stage=PipelineStage.WON,
            source="conversation",
            estimated_value=10000.0,
            currency="USD",
        ),
    ]

    rows = summarize_revenue_by_source(opportunities)

    assert len(rows) == 1
    assert rows[0].source == "conversation"
    assert rows[0].total_value == 10000.0
    assert rows[0].opportunity_count == 1


def test_grouped_by_source_and_currency_separately() -> None:
    opportunities = [
        _opportunity(
            pipeline_stage=PipelineStage.WON,
            source="conversation",
            estimated_value=1000.0,
            currency="USD",
        ),
        _opportunity(
            pipeline_stage=PipelineStage.WON,
            source="conversation",
            estimated_value=2000.0,
            currency="USD",
        ),
        _opportunity(
            pipeline_stage=PipelineStage.WON,
            source="conversation",
            estimated_value=500.0,
            currency="EUR",
        ),
        _opportunity(
            pipeline_stage=PipelineStage.WON, source=None, estimated_value=300.0, currency="USD"
        ),
    ]

    rows = {(row.source, row.currency): row for row in summarize_revenue_by_source(opportunities)}

    assert rows[("conversation", "USD")].total_value == 3000.0
    assert rows[("conversation", "USD")].opportunity_count == 2
    assert rows[("conversation", "EUR")].total_value == 500.0
    assert rows[("unknown", "USD")].total_value == 300.0


def test_includes_estimate_is_true_if_any_contributing_row_is_an_estimate() -> None:
    opportunities = [
        _opportunity(
            pipeline_stage=PipelineStage.WON,
            source="conversation",
            estimated_value=1000.0,
            currency="USD",
            is_estimated_value=False,
        ),
        _opportunity(
            pipeline_stage=PipelineStage.WON,
            source="conversation",
            estimated_value=2000.0,
            currency="USD",
            is_estimated_value=True,
        ),
    ]

    rows = summarize_revenue_by_source(opportunities)

    assert rows[0].includes_estimate is True


def test_no_won_opportunities_returns_an_empty_list() -> None:
    opportunities = [
        _opportunity(
            pipeline_stage=PipelineStage.QUALIFIED,
            source="conversation",
            estimated_value=1000.0,
            currency="USD",
        )
    ]

    assert summarize_revenue_by_source(opportunities) == []
