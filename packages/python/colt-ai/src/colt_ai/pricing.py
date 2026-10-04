"""Per-model USD pricing (CLAUDE.md §68's "usage/cost tracking").

Prices are USD per million tokens, keyed by the literal Anthropic model ID — not by
`ModelClass` — so a routing change (`AnthropicSettings.model_fast`, etc., CLAUDE.md §14.2)
costs correctly without a code change here, as long as the new model ID is priced below.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float


#: Current Anthropic API pricing, USD per 1M tokens.
_PRICING: dict[str, ModelPricing] = {
    "claude-opus-5-5": ModelPricing(4.00, 20.00),
    "claude-opus-5": ModelPricing(5.00, 25.00),
    "claude-opus-4-8": ModelPricing(5.00, 25.00),
    "claude-opus-4-7": ModelPricing(5.00, 25.00),
    "claude-opus-4-6": ModelPricing(5.00, 25.00),
    "claude-sonnet-5-5": ModelPricing(2.00, 10.00),
    "claude-sonnet-5": ModelPricing(2.00, 10.00),
    "claude-sonnet-4-6": ModelPricing(3.00, 15.00),
    "claude-haiku-4-5": ModelPricing(1.00, 5.00),
    "claude-haiku-4-5-20251001": ModelPricing(1.00, 5.00),
}


def estimate_cost_usd(*, model: str, input_tokens: int, output_tokens: int) -> float | None:
    """The call's cost in USD, or `None` when `model` has no entry above.

    `None` rather than a guess: a model Colt doesn't yet price should show up as a gap to
    fill, not a silently wrong number. Callers still record the raw token counts
    (`llm_input_tokens`/`llm_output_tokens`, §35.2) either way.
    """
    pricing = _PRICING.get(model)
    if pricing is None:
        return None
    return (input_tokens / 1_000_000) * pricing.input_per_million + (
        output_tokens / 1_000_000
    ) * pricing.output_per_million
