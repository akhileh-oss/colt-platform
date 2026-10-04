"""The AgentRun entity (CLAUDE.md §10.15) — the audit record of one agent execution.

`AgentRunStatus` is not given an explicit closed set in `CLAUDE.md` the way `LeadStatus` is
(§11.1), but `started_at`/`completed_at`/`status` describe a genuine, closed lifecycle — a run
is in progress, or it finished one of two ways — so it is modeled as a closed enum with a DB
`CHECK` constraint rather than an open string, matching the other closed-vocabulary fields this
package already enforces that way.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgentRunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentRun(BaseModel):
    """One execution of one agent — what it was asked, what it cost, and how it ended."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    agent_name: str
    agent_version: str
    model_name: str
    workflow_id: str | None = None
    workflow_run_id: str | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    prompt_version: str | None = None
    input_hash: str
    started_at: datetime
    completed_at: datetime | None = None
    status: AgentRunStatus = AgentRunStatus.RUNNING
    input_tokens: int = 0
    output_tokens: int = 0
    tool_tokens: int = 0
    estimated_cost_usd: float | None = None
    output_json: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None

    def completed(
        self,
        *,
        at: datetime,
        input_tokens: int,
        output_tokens: int,
        tool_tokens: int,
        estimated_cost_usd: float | None,
        output_json: dict[str, Any] | None,
    ) -> Self:
        return self.model_copy(
            update={
                "status": AgentRunStatus.COMPLETED,
                "completed_at": at,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "tool_tokens": tool_tokens,
                "estimated_cost_usd": estimated_cost_usd,
                "output_json": output_json,
            }
        )

    def failed(self, *, at: datetime, error_code: str, error_message: str) -> Self:
        return self.model_copy(
            update={
                "status": AgentRunStatus.FAILED,
                "completed_at": at,
                "error_code": error_code,
                "error_message": error_message,
            }
        )
