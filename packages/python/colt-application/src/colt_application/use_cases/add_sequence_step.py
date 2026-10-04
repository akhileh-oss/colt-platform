"""`AddSequenceStep` (CLAUDE.md §10.9, §10.10, Milestone 14).

Checks the campaign exists in this organization before creating a step for it, so a bad
`campaign_id` surfaces as the same `NotFoundError` every other use case raises for a missing
parent — not a raw `IntegrityError` from the database's foreign key leaking past this layer.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from colt_application.errors import NotFoundError
from colt_application.ports.campaign_repository import CampaignRepository
from colt_application.ports.sequence_step_repository import SequenceStepRepository
from colt_domain import SequenceStep


class AddSequenceStep:
    def __init__(
        self, campaigns: CampaignRepository, sequence_steps: SequenceStepRepository
    ) -> None:
        self._campaigns = campaigns
        self._sequence_steps = sequence_steps

    async def __call__(
        self,
        *,
        campaign_id: UUID,
        step_order: int,
        channel: str,
        message_strategy: str,
        delay_after_previous: int = 0,
        conditions: dict[str, Any] | None = None,
        active: bool = True,
    ) -> SequenceStep:
        if await self._campaigns.get(campaign_id) is None:
            raise NotFoundError(f"No campaign found with id {campaign_id}.")
        return await self._sequence_steps.add(
            campaign_id=campaign_id,
            step_order=step_order,
            channel=channel,
            message_strategy=message_strategy,
            delay_after_previous=delay_after_previous,
            conditions=conditions,
            active=active,
        )
