"""Tenant-scoped repository for `Message` (CLAUDE.md §10.11)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_db.mappers import message_to_domain
from colt_db.models.message import MessageModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import Message


class SqlAlchemyMessageRepository(TenantScopedRepository):
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
    ) -> Message:
        model = MessageModel(
            organization_id=self.organization_id,
            campaign_id=campaign_id,
            lead_id=lead_id,
            conversation_id=conversation_id,
            sequence_step_id=sequence_step_id,
            channel=channel,
            subject=subject,
            body=body,
            status=status,
            approval_status=approval_status,
            evidence_ids=[str(value) for value in (evidence_ids or [])],
            model_name=model_name,
            prompt_version=prompt_version,
            idempotency_key=idempotency_key,
            scheduled_at=scheduled_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return message_to_domain(model)

    async def get(self, message_id: UUID) -> Message | None:
        stmt = self._select_scoped(MessageModel).where(MessageModel.id == message_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return message_to_domain(model) if model is not None else None

    async def get_by_idempotency_key(self, idempotency_key: str) -> Message | None:
        """Look up a message by its send idempotency key (§2.9, §24.4) — the check a retried
        send workflow makes before ever attempting to send again."""
        stmt = self._select_scoped(MessageModel).where(
            MessageModel.idempotency_key == idempotency_key
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return message_to_domain(model) if model is not None else None

    async def list_by_campaign(self, campaign_id: UUID) -> list[Message]:
        stmt = (
            self._select_scoped(MessageModel)
            .where(MessageModel.campaign_id == campaign_id)
            .order_by(MessageModel.created_at)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [message_to_domain(model) for model in models]

    async def list_by_lead_and_step(
        self, lead_id: UUID, sequence_step_id: UUID | None
    ) -> list[Message]:
        """Every drafted "version" of a message for this lead/step, oldest first (Milestone 15:
        `add()` never overwrites — see this port's own docstring)."""
        stmt = (
            self._select_scoped(MessageModel)
            .where(
                MessageModel.lead_id == lead_id,
                MessageModel.sequence_step_id == sequence_step_id,
            )
            .order_by(MessageModel.created_at)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [message_to_domain(model) for model in models]
