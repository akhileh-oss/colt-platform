"""The ToolCall entity (CLAUDE.md §10.16) — the audit record of one tool invocation.

`arguments_redacted`/`result_summary` are named for what they must hold, not just what they
happen to: §10.16 is explicit that secrets must never land in tool arguments or results, so
callers are responsible for redacting before constructing this entity — it has no redaction
logic of its own, the same division of responsibility `colt_observability.redact()` draws
between structural key-based redaction and content the caller must keep out in the first place.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ToolCallStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ToolCall(BaseModel):
    """One tool invocation made during an `AgentRun`."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    agent_run_id: UUID
    organization_id: UUID
    tool_name: str
    tool_version: str
    arguments_redacted: str
    result_summary: str | None = None
    provider: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    status: ToolCallStatus = ToolCallStatus.RUNNING
    error_code: str | None = None
    latency_ms: float | None = None

    def succeeded(self, *, at: datetime, result_summary: str, latency_ms: float) -> Self:
        return self.model_copy(
            update={
                "status": ToolCallStatus.SUCCEEDED,
                "completed_at": at,
                "result_summary": result_summary,
                "latency_ms": latency_ms,
            }
        )

    def failed(self, *, at: datetime, error_code: str, latency_ms: float) -> Self:
        return self.model_copy(
            update={
                "status": ToolCallStatus.FAILED,
                "completed_at": at,
                "error_code": error_code,
                "latency_ms": latency_ms,
            }
        )
