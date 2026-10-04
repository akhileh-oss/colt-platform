"""GetLead (CLAUDE.md §2.3, §10.7).

The port is faked in-memory here — no database. `colt-db`'s integration tests separately prove
`SqlAlchemyLeadRepository` satisfies this same port against real Postgres and real RLS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_application.errors import NotFoundError
from colt_application.use_cases.get_lead import GetLead
from colt_domain import Lead

NOW = datetime.now(UTC)


class FakeLeadRepository:
    def __init__(self, leads: list[Lead]) -> None:
        self._by_id = {lead.id: lead for lead in leads}

    async def get(self, lead_id: UUID) -> Lead | None:
        return self._by_id.get(lead_id)


def _lead(*, id: UUID | None = None) -> Lead:
    return Lead(
        id=id or uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        person_id=uuid4(),
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.asyncio
async def test_returns_the_lead_when_it_exists_in_this_organization() -> None:
    lead = _lead()
    get_lead = GetLead(FakeLeadRepository([lead]))

    result = await get_lead(lead.id)

    assert result.id == lead.id


@pytest.mark.asyncio
async def test_raises_not_found_when_the_lead_does_not_exist_in_this_organization() -> None:
    get_lead = GetLead(FakeLeadRepository([]))

    with pytest.raises(NotFoundError):
        await get_lead(uuid4())
