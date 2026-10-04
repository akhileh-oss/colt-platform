from __future__ import annotations

from colt_ai.pricing import estimate_cost_usd


def test_estimate_cost_usd_for_a_priced_model() -> None:
    cost = estimate_cost_usd(
        model="claude-haiku-4-5-20251001", input_tokens=1_000_000, output_tokens=1_000_000
    )

    assert cost == 1.00 + 5.00


def test_estimate_cost_usd_is_none_for_an_unpriced_model() -> None:
    cost = estimate_cost_usd(
        model="some-future-model-nobody-has-priced-yet", input_tokens=100, output_tokens=100
    )

    assert cost is None
