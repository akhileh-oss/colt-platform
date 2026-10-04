"""The Sequence step repository port.

Tenant-scoped, like `CampaignRepository`: an implementation is bound to one `organization_id`
at construction.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from colt_domain import SequenceStep


class SequenceStepRepository(Protocol):
    async def add(
        self,
        *,
        campaign_id: UUID,
        step_order: int,
        channel: str,
        message_strategy: str,
        delay_after_previous: int = 0,
        conditions: dict[str, Any] | None = None,
        active: bool = True,
    ) -> SequenceStep: ...

    async def get(self, sequence_step_id: UUID) -> SequenceStep | None: ...

    async def list_by_campaign(self, campaign_id: UUID) -> list[SequenceStep]: ...
