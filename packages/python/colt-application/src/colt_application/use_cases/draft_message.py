"""`DraftMessage` (CLAUDE.md §10.11, §12.9, Milestone 15) — the one use case `MessagingAgent`'s
`draft_message` tool calls.

Re-validates `evidence_ids` itself (never trusts `select_evidence`'s earlier check alone — a
tool call is model-decided input at every step, CLAUDE.md §2.6), so this is the use case that
actually makes the acceptance criterion hold: "Generated messages contain only supported
factual personalization and retain evidence IDs." Every call creates a new `Message` row;
there is no `update()`. Regenerating a message for the same lead/step is therefore a new
"version" rather than an edit — the same append-only reasoning §10.8 applies to `LeadScore`,
applied here as this milestone's own documented decision (§10.11 lists no explicit version
field for Message).
"""

from __future__ import annotations

from uuid import UUID

from colt_application.errors import MessageValidationError
from colt_application.ports.evidence_repository import EvidenceRepository
from colt_application.ports.message_repository import MessageRepository
from colt_domain import Message


class DraftMessage:
    def __init__(self, messages: MessageRepository, evidence: EvidenceRepository) -> None:
        self._messages = messages
        self._evidence = evidence

    async def __call__(
        self,
        *,
        campaign_id: UUID,
        lead_id: UUID,
        channel: str,
        body: str,
        evidence_ids: list[UUID],
        subject: str | None = None,
        sequence_step_id: UUID | None = None,
        model_name: str | None = None,
        prompt_version: str | None = None,
    ) -> Message:
        if not evidence_ids:
            raise MessageValidationError(
                ["evidence_ids must not be empty — personalization must be evidence-based."]
            )
        missing = [
            str(evidence_id)
            for evidence_id in evidence_ids
            if await self._evidence.get(evidence_id) is None
        ]
        if missing:
            raise MessageValidationError(
                [f"evidence_id {value} does not exist in this organization." for value in missing]
            )
        return await self._messages.add(
            campaign_id=campaign_id,
            lead_id=lead_id,
            channel=channel,
            body=body,
            subject=subject,
            sequence_step_id=sequence_step_id,
            evidence_ids=evidence_ids,
            model_name=model_name,
            prompt_version=prompt_version,
        )
