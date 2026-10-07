"""The OpportunityAgent (CLAUDE.md §12.11): "Identify whether an interaction has enough
commercial intent to create/update an opportunity. Must not invent deal value unless configured
source/rules permit an estimate. Estimates must be labeled estimates."

§12.11 is CLAUDE.md's shortest agent entry — no input/output schema or tool list is given
(unlike `ScoringAgent` §12.7/`ReplyIntelligenceAgent` §12.10), so this milestone's own Build list
item is the specification for everything below, the same "the milestone building it makes the
documented call" reasoning `CampaignStatus`/`Urgency` already establish elsewhere.

The model's only job is `has_commercial_intent` and, optionally, an `estimated_value` — and the
`is_estimate` field a value always carries, since no "configured source/rules" exist anywhere in
this codebase to ever let a value NOT be labeled an estimate (the same "no real X" posture as
`SignalTriggerSource`, Milestone 12). Everything else — whether a duplicate opportunity already
exists for this company, what fields the new/updated row actually gets — is
`create_or_update_opportunity`'s deterministic job, never the model's, the same "model judges,
code decides" split `ScoringAgent` established for lead scoring.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, model_validator

from colt_agents.definition import AgentDefinition
from colt_config import ModelClass

AGENT_NAME = "opportunity-agent"
AGENT_VERSION = "v1"


class OpportunityAgentInput(BaseModel):
    conversation_id: UUID
    company_id: UUID
    company_name: str
    person_name: str
    lead_id: UUID | None
    primary_person_id: UUID | None
    subject: str | None
    body: str


class OpportunityDecision(BaseModel):
    has_commercial_intent: bool
    estimated_value: float | None = None
    currency: str | None = None
    #: Always `True` whenever `estimated_value` is given — see module docstring. Validated
    #: rather than merely documented, so a model that forgets to set it cannot silently produce
    #: an unlabeled figure.
    is_estimate: bool = False

    @model_validator(mode="after")
    def _estimate_is_always_labeled(self) -> OpportunityDecision:
        if self.estimated_value is not None and not self.is_estimate:
            raise ValueError(
                "An estimated_value must be labeled is_estimate=true (CLAUDE.md §12.11: "
                "'estimates must be labeled estimates') — no configured override source exists "
                "in this environment."
            )
        if self.estimated_value is not None and self.currency is None:
            raise ValueError("estimated_value requires a currency.")
        return self


OPPORTUNITY_AGENT_DEFINITION = AgentDefinition(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    purpose=(
        "Identify whether a positive conversation carries enough commercial intent to "
        "create/update an opportunity; never invent a deal value except as a labeled estimate "
        "(CLAUDE.md §12.11)."
    ),
    input_schema=OpportunityAgentInput,
    output_schema=OpportunityDecision,
    allowed_tools=frozenset({"create_or_update_opportunity"}),
    model_policy=ModelClass.FAST,
    max_tool_calls=3,
    timeout_seconds=60.0,
)
