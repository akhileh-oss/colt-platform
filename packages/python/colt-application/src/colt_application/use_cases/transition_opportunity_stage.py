"""`TransitionOpportunityStage` (CLAUDE.md §11.3, Milestone 21) — the one place an
`Opportunity.pipeline_stage` actually changes, gated by `opportunity_state.can_transition_stage`
rather than accepting any caller-supplied stage unconditionally.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.errors import InvalidOpportunityTransitionError, NotFoundError
from colt_application.opportunity_state import can_transition_stage
from colt_application.ports.opportunity_repository import OpportunityRepository
from colt_domain import Opportunity, PipelineStage


class TransitionOpportunityStage:
    def __init__(self, opportunities: OpportunityRepository) -> None:
        self._opportunities = opportunities

    async def __call__(
        self, opportunity_id: UUID, target_stage: PipelineStage, *, now: datetime
    ) -> Opportunity:
        opportunity = await self._opportunities.get(opportunity_id)
        if opportunity is None:
            raise NotFoundError(f"No opportunity found with id {opportunity_id}.")

        if not can_transition_stage(opportunity.pipeline_stage, target_stage):
            raise InvalidOpportunityTransitionError(
                opportunity.pipeline_stage.value, target_stage.value
            )

        return await self._opportunities.update_stage(opportunity_id, target_stage, at=now)
