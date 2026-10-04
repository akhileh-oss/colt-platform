"""The Milestone 09 scaffolding agent — not a product agent (CLAUDE.md §12 defines those;
Milestones 10-21 build them). This exists solely to give the agent-runtime mechanism a real,
end-to-end case to run: a real typed tool, a real lead lookup through the required
Typed-Tool → Application-Service → Repository → PostgreSQL path, and a real audit trail —
the same role `ExampleWorkflow` (Milestone 06) and `TraceCheckWorkflow` (Milestone 07) played
for their own milestones' mechanisms.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.definition import AgentDefinition
from colt_config import ModelClass

AGENT_NAME = "example-agent"
AGENT_VERSION = "v1"


class ExampleAgentInput(BaseModel):
    lead_id: UUID


class ExampleAgentOutput(BaseModel):
    summary: str
    lead_status: str


EXAMPLE_AGENT_DEFINITION = AgentDefinition(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    purpose=(
        "Milestone 09 scaffolding: prove a real agent can execute a typed tool, return "
        "schema-valid output, and produce a complete audit trail (CLAUDE.md §68)."
    ),
    input_schema=ExampleAgentInput,
    output_schema=ExampleAgentOutput,
    allowed_tools=frozenset({"get_lead"}),
    model_policy=ModelClass.FAST,
    max_tool_calls=3,
    timeout_seconds=30.0,
)
