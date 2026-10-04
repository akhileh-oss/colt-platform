"""Usage and result types the AI Gateway returns (CLAUDE.md §68's "usage/cost tracking").

Plain dataclasses rather than domain entities: these describe one provider call, not
something `colt-domain` owns or persists — a future milestone that records agent-run usage
(CLAUDE.md §10.15 `AgentRun`) reads these fields rather than redefining them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


@dataclass(frozen=True)
class RawMessage:
    """One `messages.create()` turn, for callers that need the raw content blocks — a tool-use
    loop (`colt_agents.AgentRuntime`), which must inspect `tool_use` blocks and decide what to
    do next, rather than a single validated result `generate_structured()` returns.

    `content` holds the SDK's own content-block objects (`TextBlock`, `ToolUseBlock`, ...)
    unchanged — this module does not redefine SDK response types (see the Common Pitfalls this
    codebase's `claude-api` skill reference warns about).
    """

    content: list[Any]
    stop_reason: str | None
    usage: Usage
