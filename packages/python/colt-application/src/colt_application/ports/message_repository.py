"""The Message repository port (CLAUDE.md §2.3, §10.11).

Tenant-scoped, like `CampaignRepository`. `add()` has no `update()` counterpart — Milestone 15's
own design decision (see `colt_application.use_cases.draft_message`): regenerating a message
for the same lead/step creates a new, immutable row rather than overwriting one, so a lead's
drafted messages form their own append-only "versions" history, the same pattern `LeadScore`
(§10.8) already established for scoring.

Milestone 16 adds three workflow-status mutators (`update_approval_status`,
`update_send_result`, `count_sent_since`). These do not reopen the append-only rule above: that
rule protects drafted *content* from being silently overwritten by a newer draft. A message's
approval/send status is lifecycle metadata on the one row a human or the policy engine is
actually deciding about — the same distinction `CampaignStatus` being mutable in place
(Milestone 14) already draws for `Campaign`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from colt_domain import Message


class MessageRepository(Protocol):
    async def add(
        self,
        *,
        campaign_id: UUID,
        lead_id: UUID,
        channel: str,
        body: str,
        conversation_id: UUID | None = None,
        sequence_step_id: UUID | None = None,
        subject: str | None = None,
        status: str = "DRAFT",
        approval_status: str = "PENDING",
        evidence_ids: list[UUID] | None = None,
        model_name: str | None = None,
        prompt_version: str | None = None,
        idempotency_key: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> Message: ...

    async def get(self, message_id: UUID) -> Message | None: ...

    async def get_by_idempotency_key(self, idempotency_key: str) -> Message | None: ...

    async def list_by_campaign(self, campaign_id: UUID) -> list[Message]: ...

    async def list_by_lead_and_step(
        self, lead_id: UUID, sequence_step_id: UUID | None
    ) -> list[Message]: ...

    async def update_approval_status(
        self, message_id: UUID, *, approval_status: str
    ) -> Message: ...

    async def update_send_result(
        self,
        message_id: UUID,
        *,
        status: str,
        sent_at: datetime,
        provider_message_id: str | None,
    ) -> Message: ...

    async def count_sent_since(self, campaign_id: UUID, since: datetime) -> int: ...
