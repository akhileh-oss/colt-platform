"""The MessagingAgent (CLAUDE.md §12.9): transforms a personalization strategy into a
channel-appropriate drafted message.

No send tool exists in its `allowed_tools` — per §12.9, "It may draft but should not send unless
the channel/tool permission explicitly allows it through policy," and no such policy-gated send
tool is built until Milestone 16 (Policy + Approval System). `draft_message` persists exactly
one new `Message` row per call and re-validates `evidence_ids` itself (never trusting that
`PersonalizationAgent`'s own `select_evidence` check still holds by the time this agent runs).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from colt_agents.definition import AgentDefinition
from colt_config import ModelClass

AGENT_NAME = "messaging-agent"
AGENT_VERSION = "v1"


class MessagingAgentInput(BaseModel):
    lead_id: UUID
    campaign_id: UUID
    channel: str
    angle: str
    business_relevance: str
    evidence_ids: list[UUID]
    sequence_step_id: UUID | None = None
    #: This organization's brand voice (`colt_application.brand_voice.get_brand_voice`) —
    #: an already-known fact handed in, the same pattern `ScoringAgentInput`'s component
    #: scores and `ResearchAgentInput`'s `company_name`/`company_domain` already use, since
    #: tone is a prompt-level instruction no tool call could validate deterministically.
    brand_voice: dict[str, Any] = {}


class MessagingAgentOutput(BaseModel):
    message_id: UUID
    channel: str
    subject: str | None
    body: str
    evidence_ids: list[UUID]


MESSAGING_AGENT_DEFINITION = AgentDefinition(
    name=AGENT_NAME,
    version=AGENT_VERSION,
    purpose=(
        "Transform a personalization strategy into a channel-appropriate drafted message. "
        "May draft, never send (CLAUDE.md §12.9) - no send tool is offered."
    ),
    input_schema=MessagingAgentInput,
    output_schema=MessagingAgentOutput,
    allowed_tools=frozenset({"draft_message"}),
    model_policy=ModelClass.STANDARD,
    max_tool_calls=3,
    timeout_seconds=90.0,
)
