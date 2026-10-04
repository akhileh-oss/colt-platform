"""The Person repository port (CLAUDE.md §2.3, §10.4, §22). See `CompanyRepository` for the
identity-resolution rationale behind the `find_by_*` methods.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from colt_domain import EmailStatus, Person


class PersonRepository(Protocol):
    async def add(
        self,
        *,
        company_id: UUID,
        full_name: str,
        first_name: str | None = None,
        last_name: str | None = None,
        title: str | None = None,
        seniority: str | None = None,
        department: str | None = None,
        email: str | None = None,
        email_status: EmailStatus | None = None,
        linkedin_url: str | None = None,
        location: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> Person: ...

    async def get(self, person_id: UUID) -> Person | None: ...

    async def find_by_email(self, email: str) -> Person | None: ...

    async def find_by_linkedin_url(self, linkedin_url: str) -> Person | None: ...

    async def list_by_company(self, company_id: UUID) -> list[Person]: ...

    async def find_by_provider_id(self, provider: str, provider_id: str) -> Person | None: ...

    async def update(self, person_id: UUID, **fields: Any) -> Person: ...
