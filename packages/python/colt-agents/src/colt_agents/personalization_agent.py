"""The PersonalizationAgent (CLAUDE.md §12.8): selects the most commercially relevant verified
evidence for a lead and forms a personalization strategy from it.

`PersonalizationStrategy.evidence_ids` is validated non-empty — §12.8's "no unsupported claims"
rule is structurally unviolable here, not merely a prompt instruction: there is no way to
construct a strategy that cites nothing, the same technique `DossierClaim`'s `FACT` validator
(Milestone 10) uses for research claims. The tool-call path behind it
(`select_evidence`) independently re-checks every cited id against this organization's real
`Evidence` rows before the agent can ever finalize an answer with them.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, field_validator

from colt_agents.definition import AgentDefinition
from colt_config import ModelClass

AGENT_NAME = "personalization-agent"
AGENT_VERSION = "v1"


class PersonalizationStrategy(BaseModel):
    lead_id: UUID
    evidence_ids: list[UUID]
    angle: str
    business_relevance: str

    @field_validator("evidence_ids")
    @classmethod
    def _not_empty(cls, value: list[UUID]) -> list[UUID]:
        if not value:
            raise ValueError(
                "A personalization strategy must cite at least one evidence_id — select it "
                "via select_evidence first (CLAUDE.md §12.8: 'no unsupported claims')."
            )
        return value


class PersonalizationAgentInput(BaseModel):
    lead_id: UUID
    company_name: str
    person_name: str


PERSONALIZATION_AGENT_DEFINITION = AgentDefinition(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    purpose=(
        "Select the most commercially relevant verified evidence for a lead and form a "
        "personalization strategy from it, never inventing familiarity or unsupported claims "
        "(CLAUDE.md §12.8)."
    ),
    input_schema=PersonalizationAgentInput,
    output_schema=PersonalizationStrategy,
    allowed_tools=frozenset({"list_evidence_for_lead", "select_evidence"}),
    model_policy=ModelClass.STANDARD,
    max_tool_calls=5,
    timeout_seconds=120.0,
)
