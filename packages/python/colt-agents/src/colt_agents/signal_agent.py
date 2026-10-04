"""The SignalAgent (CLAUDE.md §12.6): detects "why now" events from polled trigger sources.

Output fields are exactly §12.6's required list (`signal_type`, `summary`, `event_date`,
`source`, `confidence`, `business_implication`), plus `signal_id` (what was actually persisted)
and `rank` (computed deterministically by `record_signal`, not by the model) so a caller never
has to re-derive it.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel

from colt_agents.definition import AgentDefinition
from colt_config import ModelClass

AGENT_NAME = "signal-agent"
AGENT_VERSION = "v1"


class SignalAgentInput(BaseModel):
    company_id: UUID


class SignalAgentOutput(BaseModel):
    signal_id: UUID
    signal_type: str
    summary: str | None
    event_date: date | None
    source: str | None
    confidence: float | None
    business_implication: str | None
    rank: float


SIGNAL_AGENT_DEFINITION = AgentDefinition(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    purpose=(
        'Detect "why now" buying signals from polled trigger sources and record the strongest '
        "one found, with its business implication (CLAUDE.md §12.6)."
    ),
    input_schema=SignalAgentInput,
    output_schema=SignalAgentOutput,
    allowed_tools=frozenset({"poll_signal_sources", "record_signal"}),
    model_policy=ModelClass.STANDARD,
    max_tool_calls=10,
    timeout_seconds=120.0,
)
