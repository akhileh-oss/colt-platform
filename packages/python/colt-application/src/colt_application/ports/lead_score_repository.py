"""The LeadScore repository port (CLAUDE.md §2.3, §10.8) — append-only; no `update`.

Tenant-scoped, like `LeadRepository`: an implementation is bound to one `organization_id` at
construction.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from colt_domain import LeadScore


class LeadScoreRepository(Protocol):
    async def add(
        self,
        *,
        lead_id: UUID,
        model_version: str,
        icp_fit: float,
        persona_fit: float,
        signal_strength: float,
        timing: float,
        model_assessment: float,
        overall_score: float,
        reason_codes: list[str],
        confidence: float | None = None,
    ) -> LeadScore: ...

    async def get(self, lead_score_id: UUID) -> LeadScore | None: ...

    async def list_by_lead(self, lead_id: UUID) -> list[LeadScore]: ...
