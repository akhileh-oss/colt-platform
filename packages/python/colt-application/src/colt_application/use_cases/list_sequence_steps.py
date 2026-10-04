"""`ListSequenceSteps` (CLAUDE.md §10.9, §10.10, Milestone 14).

Checks the campaign exists first, same reasoning as `AddSequenceStep`: otherwise an unknown
`campaign_id` and a real campaign with zero steps both return an empty list, indistinguishably.
"""

from __future__ import annotations

from uuid import UUID

from colt_application.errors import NotFoundError
from colt_application.ports.campaign_repository import CampaignRepository
from colt_application.ports.sequence_step_repository import SequenceStepRepository
from colt_domain import SequenceStep


class ListSequenceSteps:
    def __init__(
        self, campaigns: CampaignRepository, sequence_steps: SequenceStepRepository
    ) -> None:
        self._campaigns = campaigns
        self._sequence_steps = sequence_steps

    async def __call__(self, campaign_id: UUID) -> list[SequenceStep]:
        if await self._campaigns.get(campaign_id) is None:
            raise NotFoundError(f"No campaign found with id {campaign_id}.")
        return await self._sequence_steps.list_by_campaign(campaign_id)
