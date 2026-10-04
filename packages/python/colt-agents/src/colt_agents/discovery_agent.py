"""The DiscoveryAgent (CLAUDE.md §12.3): finds candidate companies/people using approved
discovery providers, deduplicating against already-known records (§22) as it goes.

`allowed_tools` is `search_companies`/`search_people` (built this milestone) plus `search_web`
(§16.1's Research category, built in Milestone 10) — exactly §12.3's allowed-tools list minus
`search_news`/`search_jobs`, which no milestone has built a tool for yet; granting an agent a
tool name nothing registers would fail loudly at assembly time (`ToolRegistry.for_agent`), not
silently grant less than intended.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.definition import AgentDefinition
from colt_config import ModelClass

AGENT_NAME = "discovery-agent"
AGENT_VERSION = "v1"


class DiscoveredCompany(BaseModel):
    company_id: UUID
    name: str
    domain: str | None
    provider: str
    confidence: float


class DiscoveredPerson(BaseModel):
    person_id: UUID
    full_name: str
    title: str | None
    provider: str
    confidence: float


class DiscoveryAgentInput(BaseModel):
    icp_description: str


class DiscoveryAgentOutput(BaseModel):
    companies: list[DiscoveredCompany]
    people: list[DiscoveredPerson]


DISCOVERY_AGENT_DEFINITION = AgentDefinition(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    purpose=(
        "Find candidate companies and people matching an ICP using approved discovery "
        "providers, deduplicated against already-known records (CLAUDE.md §12.3, §22)."
    ),
    input_schema=DiscoveryAgentInput,
    output_schema=DiscoveryAgentOutput,
    allowed_tools=frozenset({"search_companies", "search_people", "search_web"}),
    model_policy=ModelClass.STANDARD,
    max_tool_calls=20,
    timeout_seconds=300.0,
)
