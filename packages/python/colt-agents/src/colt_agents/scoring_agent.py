"""The ScoringAgent (CLAUDE.md §12.7, §21): forms the one qualitative judgment call a hybrid
lead score needs, then lets deterministic application code (`score_lead`) decide the rest.

"Evaluate qualitative fit after deterministic scoring. The overall score must be reproducible
from stored inputs. Never allow 'vibes' alone to determine qualification." `icp_fit`,
`signal_strength`, and `timing` are given as already-known facts (deterministic figures other
parts of the system compute — ICP matching rules, `colt_application.signals.rank_signal`,
recent-signal recency); this agent's only distinctive job is `persona_fit` and
`model_assessment`, its own qualitative read of the lead. Everything downstream of that —
`overall_score`, `reason_codes`, qualification — is `score_lead`'s deterministic arithmetic,
never the model's.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.definition import AgentDefinition
from colt_config import ModelClass

AGENT_NAME = "scoring-agent"
AGENT_VERSION = "v1"


class ScoringAgentInput(BaseModel):
    lead_id: UUID
    icp_fit: float
    signal_strength: float
    timing: float


class ScoringAgentOutput(BaseModel):
    lead_score_id: UUID
    persona_fit: float
    model_assessment: float
    overall_score: float
    reason_codes: list[str]
    qualified: bool


SCORING_AGENT_DEFINITION = AgentDefinition(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    purpose=(
        "Evaluate a lead's qualitative fit (persona_fit, model_assessment) after deterministic "
        "scoring decides the rest - never 'vibes' alone (CLAUDE.md §12.7)."
    ),
    input_schema=ScoringAgentInput,
    output_schema=ScoringAgentOutput,
    allowed_tools=frozenset({"score_lead"}),
    model_policy=ModelClass.FAST,
    max_tool_calls=3,
    timeout_seconds=60.0,
)
