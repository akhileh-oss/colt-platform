"""The typed tool interface (CLAUDE.md §2.3, §16, §68).

A tool is data, not a subclass hierarchy: a name, a Pydantic input schema, and an async handler
that takes a validated instance of that schema and returns a validated output. Concrete tools
(`colt_agents.tools.*`) build one of these from an application-layer use case rather than
reaching into `colt-db` directly — the handler is the one place §2.3's "Typed Tool → Application
Service → Repository → PostgreSQL" path is realised in code.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    version: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[BaseModel], Awaitable[BaseModel]]

    def to_anthropic_tool(self) -> dict[str, Any]:
        """The wire shape `client.messages.create(tools=[...])` expects."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }
