"""The Organization repository port.

Organization is the tenancy root: unlike every other tenant-owned entity, there is no
`organization_id` to scope a lookup by — you look an organization up by its own identity. This
port is therefore not tenant-scoped in the way `UserRepository` and later domain repositories
are, and callers still authorize *which* organization a request may see elsewhere (never here).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from colt_domain import Organization


class OrganizationRepository(Protocol):
    async def get(self, organization_id: UUID) -> Organization | None: ...

    async def get_by_slug(self, slug: str) -> Organization | None: ...
