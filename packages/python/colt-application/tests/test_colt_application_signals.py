from __future__ import annotations

from datetime import UTC, datetime

from colt_application.signals import (
    DEFAULT_SIGNAL_TYPE_WEIGHT,
    STALE_SIGNAL_DECAY_FACTOR,
    rank_signal,
)

NOW = datetime(2026, 10, 4, tzinfo=UTC)


def test_a_fresh_high_confidence_funding_signal_ranks_highly() -> None:
    rank = rank_signal(
        signal_type="funding",
        confidence=0.9,
        event_at=datetime(2026, 10, 1, tzinfo=UTC),
        observed_at=NOW,
        now=NOW,
    )
    assert rank == 0.9 * 0.9 * 1.0


def test_a_stale_signal_is_decayed_not_zeroed() -> None:
    rank = rank_signal(
        signal_type="funding",
        confidence=0.9,
        event_at=datetime(2025, 1, 1, tzinfo=UTC),
        observed_at=NOW,
        now=NOW,
    )
    assert rank == 0.9 * 0.9 * STALE_SIGNAL_DECAY_FACTOR


def test_an_unknown_signal_type_uses_the_default_weight() -> None:
    rank = rank_signal(
        signal_type="alien_invasion", confidence=1.0, event_at=NOW, observed_at=NOW, now=NOW
    )
    assert rank == DEFAULT_SIGNAL_TYPE_WEIGHT * 1.0 * 1.0


def test_a_missing_confidence_uses_the_default() -> None:
    rank = rank_signal(signal_type="news", confidence=None, event_at=NOW, observed_at=NOW, now=NOW)
    assert rank == 0.3 * 0.5 * 1.0


def test_event_at_takes_precedence_over_observed_at_for_freshness() -> None:
    rank = rank_signal(
        signal_type="news",
        confidence=1.0,
        event_at=datetime(2025, 1, 1, tzinfo=UTC),
        observed_at=NOW,
        now=NOW,
    )
    assert rank == 0.3 * 1.0 * STALE_SIGNAL_DECAY_FACTOR


def test_a_higher_weighted_signal_type_always_outranks_a_lower_one_at_equal_confidence() -> None:
    funding_rank = rank_signal(
        signal_type="funding", confidence=0.5, event_at=NOW, observed_at=NOW, now=NOW
    )
    website_change_rank = rank_signal(
        signal_type="website_change", confidence=0.5, event_at=NOW, observed_at=NOW, now=NOW
    )
    assert funding_rank > website_change_rank
