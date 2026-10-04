"""The Lead repository port.

Tenant-scoped, like `UserRepository`: an implementation is bound to one `organization_id` at
construction and cannot be asked for a lead outside it.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from colt_domain import Lead


class LeadRepository(Protocol):
    async def get(self, lead_id: UUID) -> Lead | None: ...
