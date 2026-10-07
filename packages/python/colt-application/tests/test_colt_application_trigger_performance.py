"""Deterministic trigger (signal) performance summary (CLAUDE.md §68, Milestone 22)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from colt_application.trigger_performance import summarize_trigger_performance
from colt_domain import Opportunity, PipelineStage, Signal

NOW = datetime.now(UTC)


def _signal(*, company_id: UUID, signal_type: str, confidence: float | None = None) -> Signal:
    return Signal(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=company_id,
        signal_type=signal_type,
        confidence=confidence,
        observed_at=NOW,
        created_at=NOW,
    )


def _opportunity(*, company_id: UUID, pipeline_stage: PipelineStage) -> Opportunity:
    return Opportunity(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=company_id,
        pipeline_stage=pipeline_stage,
        created_at=NOW,
        updated_at=NOW,
    )


def test_signals_group_by_signal_type() -> None:
    company = uuid4()
    signals = [
        _signal(company_id=company, signal_type="funding_round"),
        _signal(company_id=uuid4(), signal_type="funding_round"),
        _signal(company_id=uuid4(), signal_type="leadership_change"),
    ]

    rows = {row.signal_type: row for row in summarize_trigger_performance(signals, [])}

    assert rows["funding_round"].signal_count == 2
    assert rows["funding_round"].company_count == 2
    assert rows["leadership_change"].signal_count == 1


def test_a_company_signaled_twice_is_counted_once() -> None:
    company = uuid4()
    signals = [
        _signal(company_id=company, signal_type="funding_round"),
        _signal(company_id=company, signal_type="funding_round"),
    ]

    rows = {row.signal_type: row for row in summarize_trigger_performance(signals, [])}

    assert rows["funding_round"].signal_count == 2
    assert rows["funding_round"].company_count == 1


def test_won_company_count_only_counts_signaled_companies_that_won() -> None:
    won_company = uuid4()
    other_company = uuid4()
    signals = [
        _signal(company_id=won_company, signal_type="funding_round"),
        _signal(company_id=other_company, signal_type="funding_round"),
    ]
    opportunities = [
        _opportunity(company_id=won_company, pipeline_stage=PipelineStage.WON),
        _opportunity(company_id=uuid4(), pipeline_stage=PipelineStage.WON),
    ]

    rows = {row.signal_type: row for row in summarize_trigger_performance(signals, opportunities)}

    assert rows["funding_round"].won_company_count == 1


def test_average_confidence_ignores_signals_with_no_confidence() -> None:
    signals = [
        _signal(company_id=uuid4(), signal_type="funding_round", confidence=0.8),
        _signal(company_id=uuid4(), signal_type="funding_round", confidence=None),
    ]

    rows = {row.signal_type: row for row in summarize_trigger_performance(signals, [])}

    assert rows["funding_round"].average_confidence == 0.8


def test_average_confidence_is_none_when_no_signal_carries_one() -> None:
    signals = [_signal(company_id=uuid4(), signal_type="funding_round", confidence=None)]

    rows = {row.signal_type: row for row in summarize_trigger_performance(signals, [])}

    assert rows["funding_round"].average_confidence is None
