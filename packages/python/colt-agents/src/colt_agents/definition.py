"""The agent definition contract (CLAUDE.md §12.1).

A plain frozen dataclass, not a Pydantic model: this describes one agent's static
configuration — it is written once in code, never deserialised from an external boundary, the
same reasoning `colt_ai`'s `Usage`/`GenerationResult` apply (CLAUDE.md §8.1: Pydantic is for
external/application boundaries, not every data shape).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from colt_config import ModelClass


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """Every agent must define all of §12.1's fields; none have a business-meaningful default."""

    name: str
    version: str
    purpose: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    allowed_tools: frozenset[str]
    model_policy: ModelClass
    forbidden_tools: frozenset[str] = field(default_factory=frozenset)
    max_tool_calls: int = 10
    timeout_seconds: float = 120.0
    evaluation_suite: str | None = None
