"""Repository ports `AgentRuntime` persists through (CLAUDE.md §2.7, §10.15, §10.16).

Protocols, not concrete `colt-db` imports — `colt-db`'s `SqlAlchemyAgentRunRepository` and
`SqlAlchemyToolCallRepository` satisfy these structurally, the same relationship
`colt_application.ports` has with their repository implementations. `AgentRuntime` is
constructed with whichever implementation the caller wires in (a real one against Postgres, or
a fake for a hermetic test) rather than importing `colt-db` itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from colt_domain import AgentRun, ToolCall


class AgentRunRepository(Protocol):
    async def start(
        self,
        *,
        agent_name: str,
        agent_version: str,
        model_name: str,
        input_hash: str,
        workflow_id: str | None = None,
        workflow_run_id: str | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        prompt_version: str | None = None,
    ) -> AgentRun: ...

    async def complete(
        self,
        run_id: UUID,
        *,
        at: datetime,
        input_tokens: int,
        output_tokens: int,
        tool_tokens: int,
        estimated_cost_usd: float | None,
        output_json: dict[str, Any] | None,
    ) -> AgentRun: ...

    async def fail(
        self, run_id: UUID, *, at: datetime, error_code: str, error_message: str
    ) -> AgentRun: ...


class ToolCallRepository(Protocol):
    async def start(
        self,
        *,
        agent_run_id: UUID,
        tool_name: str,
        tool_version: str,
        arguments_redacted: str,
        provider: str | None = None,
    ) -> ToolCall: ...

    async def succeed(
        self, tool_call_id: UUID, *, at: datetime, result_summary: str, latency_ms: float
    ) -> ToolCall: ...

    async def fail(
        self, tool_call_id: UUID, *, at: datetime, error_code: str, latency_ms: float
    ) -> ToolCall: ...
