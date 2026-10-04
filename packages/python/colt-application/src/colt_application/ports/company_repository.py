"""The Company repository port (CLAUDE.md §2.3, §10.3, §22).

Tenant-scoped, like `LeadRepository`: an implementation is bound to one `organization_id` at
construction. The `find_by_*` methods are identity resolution's lookups (§22's layered
matching) — `DiscoverCompany`/`EnrichCompany` (Milestone 11) call them in priority order rather
than ever merging on fuzzy name similarity.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from colt_domain import Company


class CompanyRepository(Protocol):
    async def add(
        self,
        *,
        name: str,
        domain: str | None = None,
        normalized_domain: str | None = None,
        industry: str | None = None,
        employee_count: int | None = None,
        revenue_range: str | None = None,
        country: str | None = None,
        region: str | None = None,
        city: str | None = None,
        description: str | None = None,
        website_url: str | None = None,
        linkedin_url: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> Company: ...

    async def get(self, company_id: UUID) -> Company | None: ...

    async def find_by_normalized_domain(self, normalized_domain: str) -> Company | None: ...

    async def find_by_linkedin_url(self, linkedin_url: str) -> Company | None: ...

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Company | None: ...

    async def update(self, company_id: UUID, **fields: Any) -> Company: ...
