"""Usage and result types the AI Gateway returns (CLAUDE.md §68's "usage/cost tracking").

Plain dataclasses rather than domain entities: these describe one provider call, not
something `colt-domain` owns or persists — a future milestone that records agent-run usage
(CLAUDE.md §10.15 `AgentRun`) reads these fields rather than redefining them.
"""

from __future__ import annotations

from dataclasses import dataclass

from colt_config import ModelClass


@dataclass(frozen=True)
class Usage:
    """What one Anthropic API call cost and consumed."""

    model: str
    model_class: ModelClass
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    cost_usd: float | None
    latency_ms: float
    request_id: str | None


@dataclass(frozen=True)
class GenerationResult[OutputT]:
    """A completed, validated generation plus the usage metadata it recorded."""

    output: OutputT
    usage: Usage
    stop_reason: str | None
