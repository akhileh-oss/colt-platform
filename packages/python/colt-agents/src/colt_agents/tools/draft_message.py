"""`draft_message` (CLAUDE.md §10.11, §12.9) — the one write tool `MessagingAgent` may call.

Persists exactly one new `Message` row (§10.11), never updates an existing one — a later draft
for the same lead/step is a new "version," not an edit (Milestone 15's own documented decision,
see `colt_application.use_cases.draft_message`). Re-validates `evidence_ids` itself.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from colt_agents.tool import Tool
from colt_application.use_cases.draft_message import DraftMessage

TOOL_NAME = "draft_message"
TOOL_VERSION = "v1"


class DraftMessageInput(BaseModel):
    campaign_id: UUID
    lead_id: UUID
    channel: str
    body: str
    evidence_ids: list[UUID]
    subject: str | None = None
    sequence_step_id: UUID | None = None


class DraftMessageOutput(BaseModel):
    message_id: UUID
    channel: str
    subject: str | None
    body: str
    evidence_ids: list[UUID]
    status: str


def build_draft_message_tool(draft_message: DraftMessage) -> Tool:
    async def handler(validated_input: BaseModel) -> BaseModel:
        assert isinstance(validated_input, DraftMessageInput)  # noqa: S101 - guards an
        # internal contract this tool's own `input_model` guarantees; never reachable with real
        # input.
        message = await draft_message(
            campaign_id=validated_input.campaign_id,
            lead_id=validated_input.lead_id,
            channel=validated_input.channel,
            body=validated_input.body,
            evidence_ids=validated_input.evidence_ids,
            subject=validated_input.subject,
            sequence_step_id=validated_input.sequence_step_id,
        )
        return DraftMessageOutput(
            message_id=message.id,
            channel=message.channel,
            subject=message.subject,
            body=message.body,
            evidence_ids=message.evidence_ids,
            status=message.status,
        )

    return Tool(
        name=TOOL_NAME,
        version=TOOL_VERSION,
        description=(
            "Draft one outbound message for a lead. evidence_ids must be non-empty and must "
            "already have been confirmed via select_evidence - fails if any is missing or "
            "unsupported. Persists a new DRAFT message; never sends it."
        ),
        input_model=DraftMessageInput,
        handler=handler,
    )
